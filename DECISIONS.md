# Decisions

## System Invariants

- No sale of more inventory than available.
- A cart is checked out at most once.
- A coupon is redeemed at most once.
- A coupon is generated at most once per milestone.
- An order's total is never negative.
- A retried checkout request never creates a second order or double-decrements inventory.
- A failed checkout never consumes inventory or a coupon.

All four are exercised by real concurrent threads in `backend/tests/test_concurrency.py`,
asserting on final DB state (not just HTTP response codes).

## Ambiguities and Chosen Semantics

| Ambiguity | Decision | Reasoning |
|---|---|---|
| Who can redeem a coupon? | Open pool, first-come-first-served. No customer/account concept exists. | The spec never introduces a user/account model anywhere else (carts are anonymous, identified only by UUID), so inventing one just for coupon ownership would be scope creep with no other system to hang it off. |
| Stacking multiple coupons | Not allowed — API accepts a single optional `coupon_code` string. | A list-of-coupons API implies a stacking/precedence policy (additive? multiplicative? capped?) that the spec never asks for. Single optional field keeps the discount math (`Section 5`) a one-line calculation instead of a small pricing engine. |
| Minimum order value | None. Deferred. | Nothing in the brief mentions minimums; adding one invents a business rule with no default that wouldn't be arbitrary. |
| Expiry | None. Deferred. | Same reasoning — an expiry policy needs a duration, and any value chosen would be a guess. The state machine (`AVAILABLE` → `REDEEMED`, both terminal-adjacent) has no expiry state, which keeps `Section 2`'s invariant list complete without a third code path. |
| Does a discounted order still count toward the next milestone? | Yes — every successful order counts. | The milestone counter is `COUNT(orders)` with no filter; carving out discounted orders would need a new column and a rule for *why* a rewarded customer's order counts less, which the spec never argues for. Verified explicitly in `test_discounted_order_still_counts_toward_next_milestone`. |
| Price/inventory change after item added to cart, before checkout | Cart view always shows **live** current price; no snapshot until checkout. | Standard e-commerce behavior, and it sidesteps a whole class of stale-price disputes a cart-time snapshot would create (what happens when the price *drops* before checkout — do you honor the higher cart-time price?). Checkout is the one moment a price becomes contractual, so that's where the snapshot happens (`test_checkout_snapshot_survives_price_change`). |
| Invalid vs. already-redeemed coupon code | Distinct error codes: `COUPON_NOT_FOUND` (400) vs `COUPON_ALREADY_REDEEMED` (409). | These are different failure classes for a client: one is "you typed the wrong code" (fixable by re-entering), the other is "the code was valid but is gone" (not fixable by retrying). Collapsing them into one generic "invalid coupon" error would force the frontend to show the same unhelpful message for both. |
| Coupon code format | Server-generated: `SAVE{X}-{6 random base32-ish chars}`, e.g. `SAVE10-AB12CD`. | Human-readable (communicates the discount at a glance) but non-sequential, so a client can't enumerate codes by incrementing an integer. |
| Milestone generation semantics | Each admin call advances **at most one** milestone: `next_milestone = MAX(milestone_number)+1`; requires `COUNT(orders) >= next_milestone * N`. | Keeps generation one-coupon-per-call regardless of how many milestones have piled up since the last call, which makes the operation idempotent-ish (repeated calls after a stretch of orders just walk forward one milestone at a time) and trivially auditable — `milestone_number` is a dense, gapless sequence with a `UNIQUE` constraint doing the concurrency-safety work (`Section 9`). |

## Material Design Decisions

### 1. SQLite + WAL vs. an in-memory store

- **Options:** in-memory dict/list (fastest to write, no persistence, no real
  concurrency semantics to test), SQLite (file-based, real transactions, real locking
  to reason about), Postgres (production-grade, but a heavier dependency for a
  take-home).
- **Choice:** SQLite in WAL mode, `busy_timeout=5000`, commit-retry wrapper.
- **Why:** the entire assignment is about *proving* correctness under concurrency —
  an in-memory structure with a Python-level lock would trivially satisfy the
  invariants without exercising any of the interesting failure modes (lock
  contention, "database is locked", transaction rollback semantics) that a real
  datastore has. SQLite gives genuine ACID transactions and genuine writer
  contention under `ThreadPoolExecutor`-driven concurrency tests, which is the
  actual thing being tested, while staying a single dependency-free file.
- **Consequences:** SQLite only allows one writer at a time even in WAL mode, so
  under heavy concurrent load requests serialize on writes rather than truly
  parallelizing. That's fine for this scope (the tests assert correctness, not
  throughput) and is explicitly called out as the first thing to change for scale
  (see "Evolution to Multiple Instances" below).

### 2. Integer minor-unit money vs. Decimal/float

- **Options:** `float` (fast, universally supported, but binary floating point
  cannot represent most decimal fractions exactly — `0.1 + 0.2 != 0.3`),
  `Decimal` end-to-end (exact, but SQLite has no native arbitrary-precision decimal
  column type, so it would round-trip through TEXT or REAL anyway), integer minor
  units (paise).
- **Choice:** every monetary column is `INTEGER` (paise). `Decimal` appears in
  exactly one place — computing the coupon discount — and is cast to `int`
  immediately after rounding.
- **Why:** integers have no representation error, SQLite's `INTEGER` type is exact
  and indexed cheaply, and arithmetic (`sum`, comparisons, `WHERE inventory >= qty`)
  is trivial. Confining `Decimal` to one function means there's exactly one place
  in the codebase where rounding behavior needs to be tested (`test_money.py`).
- **Consequences:** every response has to convert back to a display string
  (`money.py:format_minor`), and that conversion has to happen consistently
  everywhere a price is serialized — one easy place to introduce a bug if a new
  endpoint forgets it. Mitigated by funneling all money output through the same
  `format_minor` helper rather than re-implementing the divide-by-100 formatting
  per endpoint.

### 3. Atomic conditional UPDATE vs. SELECT-then-UPDATE with explicit locking

- **Options:** `SELECT ... FOR UPDATE` (not supported cleanly by SQLite),
  application-level mutex/lock (works within one process, useless across
  multiple instances or even multiple worker threads sharing nothing), a plain
  `SELECT` then `UPDATE` (has a check-then-act race unless something else
  serializes it), or folding the precondition into the `UPDATE ... WHERE` clause
  and reading `rowcount`.
- **Choice:** the conditional `UPDATE` pattern, used identically for cart
  claiming, inventory decrement, and coupon redemption.
- **Why:** the check and the write happen as a single atomic statement regardless
  of the database's isolation level — there's no window between "check" and "act"
  for another transaction to interleave. It's also portable: the same pattern is
  correct, unchanged, if this moves to Postgres under MVCC.
- **Consequences:** error messages have to be reconstructed *after* the failed
  `UPDATE` (a second `SELECT` to find out *why* `rowcount` was 0 — not enough
  stock vs. product doesn't exist vs. coupon already gone), which is a small extra
  read per failure path but keeps the write path itself a single round-trip.

### 4. Dual idempotency (cart-state + Idempotency-Key) vs. either alone

- **Options:** rely only on cart state (`OPEN`→`CHECKED_OUT` is itself
  idempotent — a second checkout call against a `CHECKED_OUT` cart just replays
  the order), rely only on a client-supplied `Idempotency-Key` header (industry
  standard, e.g. Stripe), or both.
- **Choice:** both, layered — cart-state as the structural guarantee that always
  applies, `Idempotency-Key` as an optional exact-replay guarantee on top.
- **Why:** they solve different retry scenarios. Cart-state handles "client
  retried without sending any special header" (the common case — a mobile app
  that just re-POSTs on a timeout). `Idempotency-Key` handles "client wants a
  byte-for-byte identical response on retry, including the same HTTP status code"
  (200 on first success would otherwise become 200 on replay too, whereas
  cart-state alone always demotes a replay to 200 even if the original was 201 —
  which is arguably correct REST semantics, but not what an `Idempotency-Key`
  client contractually expects). Relying on only one wouldn't cover both.
- **Consequences:** this is the one place where a genuine, non-obvious
  concurrency bug showed up during testing (see "AI Usage" below) — multiple
  concurrent *losers* of the cart-claim race can all reach the
  `idempotency_keys` INSERT for the same key at roughly the same moment, so that
  insert has to itself tolerate a concurrent racer winning it first, rather than
  raising.

### 5. No separate coupon "reservation" state vs. an explicit RESERVED status

- **Options:** add a third coupon status (`RESERVED`) that's set before
  inventory/other checks run and only promoted to `REDEEMED` on final success, with
  a cleanup path to revert `RESERVED`→`AVAILABLE` on failure; or rely on
  transaction rollback and do the real `REDEEMED` write only once everything else
  has already succeeded.
- **Choice:** no reservation state — coupon redemption happens after inventory
  decrement succeeds, and it's part of the same transaction as everything else.
- **Why:** a `RESERVED` state exists to protect against a coupon being "stuck"
  if the process crashes mid-checkout with no rollback — but with everything in
  one DB transaction, a crash *is* a rollback (SQLite either commits the whole
  transaction or none of it). Adding `RESERVED` would require reasoning about a
  cleanup job for abandoned reservations, which is a problem that doesn't exist
  here.
- **Consequences:** this only works because the transaction really is one unit —
  if the checkout logic is ever split across multiple network calls (e.g. reserve
  inventory in one service, redeem the coupon in another), this decision would
  need to be revisited with an actual saga/reservation pattern.

### 6. One-milestone-per-generate-call vs. batch-generating all owed coupons at once

- **Options:** if `COUNT(orders)` implies 3 milestones are owed (admin hasn't
  called generate in a while), either generate all 3 coupons in one call, or
  generate exactly 1 and require 3 separate calls.
- **Choice:** exactly one coupon per call, advancing `next_milestone` by 1 each
  time.
- **Why:** "generate" reads as an imperative, singular admin action in the spec
  (`POST /admin/coupons/generate` → one coupon in the response body, not a list).
  Batch-generating would also change the response shape (list vs. single object)
  and complicate the concurrency story: the `UNIQUE(milestone_number)` constraint
  cleanly rejects a *duplicate* insert, but "insert N rows, some of which might
  already exist" is a fundamentally messier operation to make concurrency-safe.
- **Consequences:** an admin who lets orders pile up needs to call the endpoint
  once per un-rewarded milestone. That's a minor UX friction for an admin
  tool, not a customer-facing one, so it's an acceptable trade for the simpler,
  more auditable semantics.

## Transaction, Concurrency, and Idempotency Strategy

Checkout is a single DB transaction: claim the cart first (this is the actual
concurrency gate — see `Section 3`'s reasoning, reproduced verbatim as a comment in
`checkout_service.py` since it's load-bearing), decrement inventory per line with a
conditional `UPDATE`, redeem the coupon (if any) the same way, insert the order and
its line-item snapshots, and commit once. Any raised exception happens before that
single commit, so the whole transaction rolls back — no partial decrements, no
orphaned orders, no burned coupons on an unrelated failure.

Built exactly per the spec's pseudocode (`Section 8`), with one addition made during
testing: the idempotency-key write in the "loser of the cart-claim race" branch has
to tolerate a `sqlite3.IntegrityError` from a *concurrent* loser inserting the same
key first (see `_store_idempotency_key_safe` in `checkout_service.py`) — the spec's
pseudocode doesn't show this because it's a second-order race (a race to store the
result of losing a race), only visible once you actually fire concurrent requests at
it (`test_duplicate_checkout_retry_same_cart`).

## Money and Rounding Rules

All monetary DB columns are `INTEGER` minor units (paise). `Decimal` +
`ROUND_HALF_UP` is used only to compute the coupon discount, then immediately cast
back to `int` and clamped to never exceed the subtotal — so `total_minor` is
structurally never negative (it's `subtotal - min(discount, subtotal)`). API
responses serialize money as formatted strings (`"199.00"`) alongside a shared
`"currency": "INR"` field, never as raw minor-unit integers.

## Error Model

Every error is a subclass of `AppError` carrying its own error `code`, HTTP status,
and structured `details` dict, registered once via a single FastAPI exception
handler that renders the `{"error": {code, message, details}}` envelope. Chose
distinguishable codes over generic HTTP statuses because several different failure
reasons legitimately share one HTTP status (e.g. `COUPON_NOT_FOUND` and
`CART_NOT_FOUND` are both 404s but need completely different frontend copy and
recovery actions), and a client dispatching on `error.code` is far more robust
against future changes than one parsing `error.message` strings.

## Implemented vs. Deferred

**Implemented:** full cart CRUD, single-transaction checkout with inventory and
coupon guards, dual idempotency, milestone coupon generation and redemption, admin
revenue report, all four required concurrency tests, a five-view frontend wired to
the live API, OpenAPI export.

**Deferred** (and why, and what I'd do next): auth/authz (no user/account concept
anywhere in the spec — would need to be designed from scratch, not bolted on),
coupon expiry and minimum order value (no default value the spec implies —
see the ambiguity table), multi-currency (money is minor-unit integers already,
so this is "mostly" just adding a `currency` column to `products`/`orders` instead
of a hardcoded `"INR"` — the hard part, exchange-rate-at-time-of-order, is genuinely
out of scope), payment gateway integration (checkout as specified has no payment
step — it's inventory + pricing only), refunds/cancellations (would need an
`orders.status` state machine that doesn't exist yet, plus inventory
restoration logic), rate limiting (an infra/gateway concern, not application
logic), structured logging/tracing (would matter a lot once this runs as more than
one instance — see below).

## Evolution to Multiple Instances and Production Scale

- Swap SQLite for Postgres: the atomic conditional-`UPDATE` pattern
  (`Section 3`) is correct **unchanged** under Postgres MVCC — this was a design
  goal, not an accident, and is why `SELECT ... FOR UPDATE`-style explicit locking
  was avoided even though SQLite can't do it cleanly.
- Move the `idempotency_keys` table from local SQLite to a shared store (a
  Postgres table, or Redis with a TTL) so any instance can see any other
  instance's recent requests — right now, two instances behind a load balancer
  with their own SQLite files would each have a blind spot for the other's
  idempotency keys.
- Consider `SELECT ... FOR UPDATE` or `SERIALIZABLE` isolation on Postgres for
  defense in depth, once the app is no longer incidentally relying on SQLite's
  single-writer serialization as a safety net it never asked for.
- Connection pooling (pgbouncer), a read replica for the report endpoint (it's
  pure reads, no reason to compete with checkout traffic for the primary),
  and an outbox pattern if other services need to react to orders/coupons being
  created.

## AI Usage

Built with Claude (Sonnet 5) end-to-end, working directly in the repo rather than
via a chat-and-paste workflow. Two concrete things worth naming rather than a vague
"AI helped a lot":

1. **A real bug the model introduced and then found by actually running the app.**
   The frontend's `api.js` merged fetch headers as
   `{ headers: {...}, ...options }` — because `options` itself also carries a
   `headers` key, spreading the caller's raw `options` object *after* the
   carefully-merged `headers` field silently threw the merge away. Every checkout
   call sends an `Idempotency-Key` header, so in practice this meant
   `Content-Type: application/json` was dropped from *every* checkout request,
   and the backend received the JSON body as a raw string rather than parsing it,
   failing with a 422. This didn't show up in the backend's own pytest suite
   (httpx's `TestClient` sets `Content-Type` correctly regardless of what the
   test asks for) — it only surfaced when actually clicking "Place order" in a
   browser against the real running backend. I reproduced it independently with a
   raw `urllib` request missing the header to confirm the root cause before
   fixing the merge order (destructure `headers` out of `options` first, then
   spread the rest, then set `headers` last, so nothing can clobber it).
2. **A design-time judgment call I redirected.** The initial instinct for
   isolating pytest DB state was to reuse one process-wide SQLAlchemy engine
   across tests and just delete rows between tests — but `db.py`'s engine, and
   the WAL pragma applied on connect, are module-level singletons by design (per
   the spec's own requirement that the pragma be "set on every connection"), so
   sharing one engine across tests would mean every test shares one SQLite file
   and one set of `PRAGMA` settings, making tests interfere with each other's
   inventory/order counts. I redirected this toward per-test module reloading
   (`sys.modules` eviction + a fresh temp file + fresh env vars in
   `conftest.py`'s `client` fixture) so each test gets a genuinely fresh engine
   bound to a genuinely fresh file, which is what the concurrency tests need
   to assert clean starting inventory counts.

Also corrected along the way: `app.on_event("startup")` (deprecated in current
FastAPI) was rewritten as a `lifespan` context manager; `ruff`'s `B008` rule
(flags `Depends(...)` as an argument default) had to be explicitly silenced in
`pyproject.toml` since that's the standard, intentional FastAPI dependency-injection
pattern, not a bug.

## What I'd Examine First With Two More Hours

- Property-based tests (Hypothesis) for the discount rounding function across a
  much wider space of `(subtotal, percent)` pairs than the three hand-picked edge
  cases currently covered.
- Load-test the concurrency endpoints at higher parallelism (50-100 concurrent
  requests rather than 5-10) to see where SQLite's single-writer serialization
  starts to show up as request latency rather than just correctness.
- Structured logging (request id, cart id, order id as consistent fields) — right
  now there's no observability story at all beyond uvicorn's access log.
- A Postman collection alongside the exported `openapi.json`, generated from a
  scripted run against a seeded instance, so error responses are demonstrated
  too, not just happy paths.

## Time Spent

Built in a single focused session: roughly 45 minutes on schema/models/config,
90 minutes on the checkout transaction and services layer (including finding and
fixing the idempotency-key race), 45 minutes on coupons/report, 45 minutes writing
the test suite (unit + integration + concurrency), 60 minutes on the frontend, and
30 minutes manually exercising the full app in a browser against the live backend
(which is where both real bugs above were actually found), plus this document.
