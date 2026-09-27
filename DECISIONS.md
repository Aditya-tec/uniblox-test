# Decisions

## System Invariants

- No sale of more inventory than available.
- A cart is checked out at most once.
- A coupon is redeemed at most once.
- A coupon is generated at most once per milestone.
- An order's total is never negative.
- A retried checkout request never creates a second order or double-decrements inventory.
- A failed checkout never consumes inventory or a coupon.

I exercise all four with real concurrent threads in `backend/tests/test_concurrency.py`,
asserting on final DB state rather than just HTTP response codes.

## Ambiguities and Chosen Semantics

| Ambiguity | Decision | Reasoning |
|---|---|---|
| Who can redeem a coupon? | Open pool, first-come-first-served. No customer/account concept exists. | I don't introduce a user/account model anywhere else in the system (carts are anonymous, identified only by UUID), so inventing one just for coupon ownership would be scope creep with nothing else to hang it off. |
| Stacking multiple coupons | Not allowed — API accepts a single optional `coupon_code` string. | A list-of-coupons API implies a stacking/precedence policy (additive? multiplicative? capped?) that nothing in the brief asks for. I kept a single optional field so the discount math (`Section 5`) stays a one-line calculation instead of a small pricing engine. |
| Minimum order value | None. Deferred. | Nothing in the brief mentions minimums; I'd rather leave it out than invent a business rule with no default that wouldn't be arbitrary. |
| Expiry | None. Deferred. | Same reasoning — an expiry policy needs a duration, and any value I picked would be a guess. I kept the coupon state machine (`AVAILABLE` → `REDEEMED`) free of a third expiry state so the invariant list stays complete without a code path I can't justify. |
| Does a discounted order still count toward the next milestone? | Yes — every successful order counts. | The milestone counter is `COUNT(orders)` with no filter; carving out discounted orders would need a new column and a rule for *why* a rewarded customer's order counts less, which I don't have a justification for. I verified this explicitly in `test_discounted_order_still_counts_toward_next_milestone`. |
| Price/inventory change after item added to cart, before checkout | Cart view always shows **live** current price; no snapshot until checkout. | This is standard e-commerce behavior, and it sidesteps a whole class of stale-price disputes a cart-time snapshot would create (what happens when the price *drops* before checkout — do I honor the higher cart-time price?). I treat checkout as the one moment a price becomes contractual, so that's where I take the snapshot (`test_checkout_snapshot_survives_price_change`). |
| Invalid vs. already-redeemed coupon code | Distinct error codes: `COUPON_NOT_FOUND` (400) vs `COUPON_ALREADY_REDEEMED` (409). | These are different failure classes for a client: one is "you typed the wrong code" (fixable by re-entering), the other is "the code was valid but is gone" (not fixable by retrying). Collapsing them into one generic "invalid coupon" error would force the frontend to show the same unhelpful message for both, so I kept them distinct. |
| Coupon code format | Server-generated: `SAVE{X}-{6 random base32-ish chars}`, e.g. `SAVE10-AB12CD`. | I wanted something human-readable (communicates the discount at a glance) but non-sequential, so a client can't enumerate codes by incrementing an integer. |
| Milestone generation semantics | Each admin call advances **at most one** milestone: `next_milestone = MAX(milestone_number)+1`; requires `COUNT(orders) >= next_milestone * N`. | I wanted generation to stay one-coupon-per-call regardless of how many milestones have piled up since the last call, which makes the operation idempotent-ish (repeated calls after a stretch of orders just walk forward one milestone at a time) and trivially auditable — `milestone_number` is a dense, gapless sequence, and I let the `UNIQUE` constraint do the concurrency-safety work (`Section 9`). |

## Material Design Decisions

### 1. SQLite + WAL vs. an in-memory store

- **Options:** in-memory dict/list (fastest to write, no persistence, no real
  concurrency semantics to test), SQLite (file-based, real transactions, real locking
  to reason about), Postgres (production-grade, but a heavier dependency for a
  take-home).
- **Choice:** I went with SQLite in WAL mode, `busy_timeout=5000`, and a commit-retry
  wrapper.
- **Why:** this whole assignment is about *proving* correctness under concurrency —
  an in-memory structure with a Python-level lock would trivially satisfy the
  invariants without exercising any of the interesting failure modes (lock
  contention, "database is locked", transaction rollback semantics) that a real
  datastore has. SQLite gives me genuine ACID transactions and genuine writer
  contention under `ThreadPoolExecutor`-driven concurrency tests, which is the
  actual thing I'm testing, while staying a single dependency-free file.
- **Consequences:** SQLite only allows one writer at a time even in WAL mode, so
  under heavy concurrent load requests serialize on writes rather than truly
  parallelizing. I'm fine with that for this scope (my tests assert correctness,
  not throughput), and I call it out explicitly as the first thing I'd change for
  scale (see "Evolution to Multiple Instances" below).

### 2. Integer minor-unit money vs. Decimal/float

- **Options:** `float` (fast, universally supported, but binary floating point
  cannot represent most decimal fractions exactly — `0.1 + 0.2 != 0.3`),
  `Decimal` end-to-end (exact, but SQLite has no native arbitrary-precision decimal
  column type, so it would round-trip through TEXT or REAL anyway), integer minor
  units (paise).
- **Choice:** every monetary column is `INTEGER` (paise). I only use `Decimal` in
  exactly one place — computing the coupon discount — and cast it to `int`
  immediately after rounding.
- **Why:** integers have no representation error, SQLite's `INTEGER` type is exact
  and indexed cheaply, and arithmetic (`sum`, comparisons, `WHERE inventory >= qty`)
  is trivial. By confining `Decimal` to one function, there's exactly one place in
  the codebase where I need to test rounding behavior (`test_money.py`).
- **Consequences:** every response has to convert back to a display string
  (`money.py:format_minor`), and I have to apply that conversion consistently
  everywhere a price is serialized — an easy place to introduce a bug if I forget
  it on a new endpoint. I mitigated that by funneling all money output through the
  same `format_minor` helper rather than re-implementing the divide-by-100
  formatting per endpoint.

### 3. Atomic conditional UPDATE vs. SELECT-then-UPDATE with explicit locking

- **Options:** `SELECT ... FOR UPDATE` (not supported cleanly by SQLite),
  application-level mutex/lock (works within one process, useless across
  multiple instances or even multiple worker threads sharing nothing), a plain
  `SELECT` then `UPDATE` (has a check-then-act race unless something else
  serializes it), or folding the precondition into the `UPDATE ... WHERE` clause
  and reading `rowcount`.
- **Choice:** I used the conditional `UPDATE` pattern identically for cart
  claiming, inventory decrement, and coupon redemption.
- **Why:** the check and the write happen as a single atomic statement regardless
  of the database's isolation level — there's no window between "check" and "act"
  for another transaction to interleave. It's also portable: the same pattern
  stays correct, unchanged, if I move this to Postgres under MVCC.
- **Consequences:** I have to reconstruct error messages *after* the failed
  `UPDATE` (a second `SELECT` to find out *why* `rowcount` was 0 — not enough
  stock vs. product doesn't exist vs. coupon already gone), which is a small extra
  read per failure path but keeps the write path itself a single round-trip.

### 4. Dual idempotency (cart-state + Idempotency-Key) vs. either alone

- **Options:** rely only on cart state (`OPEN`→`CHECKED_OUT` is itself
  idempotent — a second checkout call against a `CHECKED_OUT` cart just replays
  the order), rely only on a client-supplied `Idempotency-Key` header (industry
  standard, e.g. Stripe), or both.
- **Choice:** I layered both — cart-state as the structural guarantee that always
  applies, `Idempotency-Key` as an optional exact-replay guarantee on top.
- **Why:** they solve different retry scenarios. Cart-state handles "client
  retried without sending any special header" (the common case — a mobile app
  that just re-POSTs on a timeout). `Idempotency-Key` handles "client wants a
  byte-for-byte identical response on retry, including the same HTTP status code"
  (cart-state alone always demotes a replay to 200 even if the original was 201 —
  arguably correct REST semantics, but not what an `Idempotency-Key` client
  contractually expects). Relying on only one wouldn't cover both cases.
- **Consequences:** this is the one place where I ran into a genuine, non-obvious
  concurrency bug during testing (see the testing notes at the end of this
  document for how it surfaced) — multiple concurrent *losers* of the cart-claim
  race can all reach the `idempotency_keys` INSERT for the same key at roughly the
  same moment, so I had to make that insert itself tolerate a concurrent racer
  winning it first, rather than raising.

### 5. No separate coupon "reservation" state vs. an explicit RESERVED status

- **Options:** add a third coupon status (`RESERVED`) that's set before
  inventory/other checks run and only promoted to `REDEEMED` on final success, with
  a cleanup path to revert `RESERVED`→`AVAILABLE` on failure; or rely on
  transaction rollback and do the real `REDEEMED` write only once everything else
  has already succeeded.
- **Choice:** I skipped a reservation state — coupon redemption happens after
  inventory decrement succeeds, as part of the same transaction as everything
  else.
- **Why:** a `RESERVED` state exists to protect against a coupon being "stuck"
  if the process crashes mid-checkout with no rollback — but with everything in
  one DB transaction, a crash *is* a rollback (SQLite either commits the whole
  transaction or none of it). Adding `RESERVED` would mean reasoning about a
  cleanup job for abandoned reservations, a problem I don't actually have here.
- **Consequences:** this only works because the transaction really is one unit —
  if I ever split checkout logic across multiple network calls (e.g. reserve
  inventory in one service, redeem the coupon in another), I'd need to revisit
  this with an actual saga/reservation pattern.

### 6. One-milestone-per-generate-call vs. batch-generating all owed coupons at once

- **Options:** if `COUNT(orders)` implies 3 milestones are owed (admin hasn't
  called generate in a while), either generate all 3 coupons in one call, or
  generate exactly 1 and require 3 separate calls.
- **Choice:** I generate exactly one coupon per call, advancing `next_milestone`
  by 1 each time.
- **Why:** "generate" reads as an imperative, singular admin action in the spec
  (`POST /admin/coupons/generate` → one coupon in the response body, not a list).
  Batch-generating would also change the response shape (list vs. single object)
  and complicate the concurrency story: the `UNIQUE(milestone_number)` constraint
  cleanly rejects a *duplicate* insert, but "insert N rows, some of which might
  already exist" is a fundamentally messier operation to make concurrency-safe.
- **Consequences:** an admin who lets orders pile up needs to call the endpoint
  once per un-rewarded milestone. I judged that a minor UX friction for an admin
  tool (not a customer-facing one) worth trading for simpler, more auditable
  semantics.

## Transaction, Concurrency, and Idempotency Strategy

I built checkout as a single DB transaction: claim the cart first (the actual
concurrency gate — I reproduced this reasoning verbatim as a comment in
`checkout_service.py` since it's load-bearing), decrement inventory per line with a
conditional `UPDATE`, redeem the coupon (if any) the same way, insert the order and
its line-item snapshots, and commit once. Any exception I raise happens before that
single commit, so the whole transaction rolls back — no partial decrements, no
orphaned orders, no burned coupons on an unrelated failure.

I built this exactly per the spec's pseudocode (`Section 8`), with one addition I
made during testing: the idempotency-key write in the "loser of the cart-claim
race" branch has to tolerate a `sqlite3.IntegrityError` from a *concurrent* loser
inserting the same key first (see `_store_idempotency_key_safe` in
`checkout_service.py`) — the spec's pseudocode doesn't show this because it's a
second-order race (a race to store the result of losing a race) that I only found
once I actually fired concurrent requests at it (`test_duplicate_checkout_retry_same_cart`).

## Money and Rounding Rules

I made every monetary DB column an `INTEGER` minor unit (paise). `Decimal` +
`ROUND_HALF_UP` is used only to compute the coupon discount, then immediately cast
back to `int` and clamped to never exceed the subtotal — so `total_minor` is
structurally never negative (it's `subtotal - min(discount, subtotal)`). I
serialize money in API responses as formatted strings (`"199.00"`) alongside a
shared `"currency": "INR"` field, never as raw minor-unit integers.

## Error Model

I modeled every error as a subclass of `AppError` carrying its own error `code`,
HTTP status, and structured `details` dict, registered once via a single FastAPI
exception handler that renders the `{"error": {code, message, details}}` envelope.
I chose distinguishable codes over generic HTTP statuses because several different
failure reasons legitimately share one HTTP status (e.g. `COUPON_NOT_FOUND` and
`CART_NOT_FOUND` are both 404s but need completely different frontend copy and
recovery actions), and a client dispatching on `error.code` is far more robust
against future changes than one parsing `error.message` strings.

## Implemented vs. Deferred

**Implemented:** full cart CRUD, single-transaction checkout with inventory and
coupon guards, dual idempotency, milestone coupon generation and redemption, admin
revenue report, all four required concurrency tests, a five-view frontend wired to
the live API, OpenAPI export.

**Deferred** (and why, and what I'd do next): auth/authz (no user/account concept
anywhere in the spec — I'd need to design this from scratch, not bolt it on),
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

- I'd swap SQLite for Postgres: the atomic conditional-`UPDATE` pattern
  (`Section 3`) is correct **unchanged** under Postgres MVCC — that was a design
  goal, not an accident, and it's why I avoided `SELECT ... FOR UPDATE`-style
  explicit locking even though SQLite can't do it cleanly.
- I'd move the `idempotency_keys` table from local SQLite to a shared store (a
  Postgres table, or Redis with a TTL) so any instance can see any other
  instance's recent requests — right now, two instances behind a load balancer
  with their own SQLite files would each have a blind spot for the other's
  idempotency keys.
- I'd consider `SELECT ... FOR UPDATE` or `SERIALIZABLE` isolation on Postgres for
  defense in depth, once the app is no longer incidentally relying on SQLite's
  single-writer serialization as a safety net it never asked for.
- I'd add connection pooling (pgbouncer), a read replica for the report endpoint
  (it's pure reads, no reason to compete with checkout traffic for the primary),
  and an outbox pattern if other services need to react to orders/coupons being
  created.

## AI Usage

I built this with Claude (Sonnet 5) as a pair-programming tool, working directly in
the repo rather than a chat-and-paste workflow. Two things worth naming
specifically rather than a vague "AI helped a lot":

1. **A header-merge bug I found and traced during manual browser testing.** After
   the backend's own test suite passed, I clicked through the actual checkout flow
   in a browser and hit a 422 on every "Place order" click. I traced it to
   `api.js`'s `request()` helper, which merged fetch headers as
   `{ headers: {...}, ...options }` — since `options` itself also carries a
   `headers` key, spreading the caller's raw `options` object *after* the
   carefully-merged `headers` field silently threw the merge away. Every checkout
   call sends an `Idempotency-Key` header, so this meant
   `Content-Type: application/json` was dropped from *every* checkout request, and
   the backend received the JSON body as a raw string instead of parsing it. This
   didn't show up in the backend's pytest suite because httpx's `TestClient` sets
   `Content-Type` correctly regardless of what the test asks for — it only
   surfaced once I actually exercised the UI against the live backend. I confirmed
   the root cause independently with a raw `urllib` request missing the header
   before directing the fix: destructure `headers` out of `options` first, spread
   the rest, then set `headers` last so nothing can clobber it.
2. **A design-time call I redirected.** The first instinct for isolating pytest DB
   state was to reuse one process-wide SQLAlchemy engine across tests and just
   delete rows between tests. I pushed back on that — `db.py`'s engine, and the
   WAL pragma applied on connect, are module-level singletons by design (the spec
   itself requires the pragma be "set on every connection"), so sharing one engine
   across tests would mean every test shares one SQLite file and one set of
   `PRAGMA` settings, letting tests interfere with each other's inventory/order
   counts. I redirected it toward per-test module reloading instead (`sys.modules`
   eviction + a fresh temp file + fresh env vars in `conftest.py`'s `client`
   fixture), so each test gets a genuinely fresh engine bound to a genuinely fresh
   file — which is what the concurrency tests need to assert clean starting
   inventory counts.

I also had it correct a couple of smaller things along the way:
`app.on_event("startup")` (deprecated in current FastAPI) got rewritten as a
`lifespan` context manager, and I had `ruff`'s `B008` rule (which flags
`Depends(...)` as an argument default) explicitly silenced in `pyproject.toml`
since that's the standard, intentional FastAPI dependency-injection pattern, not a
bug.

## What I'd Examine First With Two More Hours

- Property-based tests (Hypothesis) for the discount rounding function across a
  much wider space of `(subtotal, percent)` pairs than the three hand-picked edge
  cases I currently cover.
- Load-test the concurrency endpoints at higher parallelism (50-100 concurrent
  requests rather than 5-10) to see where SQLite's single-writer serialization
  starts to show up as request latency rather than just correctness.
- Structured logging (request id, cart id, order id as consistent fields) — right
  now there's no observability story at all beyond uvicorn's access log.
- A Postman collection alongside the exported `openapi.json`, generated from a
  scripted run against a seeded instance, so error responses are demonstrated
  too, not just happy paths.

## Time Spent

I spent a single focused working session on the original build: roughly 45 minutes
directing and reviewing schema/models/config, 90 minutes on the checkout
transaction and services layer (including tracking down and directing the fix for
the idempotency-key race), 45 minutes on coupons/report, 45 minutes on the test
suite (unit + integration + concurrency), 60 minutes on the frontend, and 30
minutes manually testing the full app in a browser against the live backend
myself — which is where I actually found both bugs documented above — plus
writing this document.

**Follow-up session (post-submission polish), roughly 90 minutes total:**
rewriting this document's voice to first-person engineering reasoning while
verifying no technical fact changed (~20 minutes); building `examples.http` and
writing a throwaway verification script to run every example against the live
backend before committing it, rather than hand-typing expected responses
(~30 minutes); setting up the GitHub Actions CI workflow, running the exact
lint/format/test commands locally first, then confirming the actual run went
green via the GitHub API and fetching the badge SVG directly to confirm it
rendered "passing" rather than assuming (~25 minutes); and adding a
`python-dotenv` loader so `backend/.env` is actually read (the README had
instructed copying `.env.example` to `.env`, but nothing previously loaded it),
verified with a real test `.env` file and a full test-suite re-run (~10 minutes).
