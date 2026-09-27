# Reliable Checkout & Rewards Service

![CI](https://github.com/Aditya-tec/uniblox-test/actions/workflows/ci.yml/badge.svg)

A small e-commerce checkout API (FastAPI + SQLite) plus a React frontend, built around
correctness under concurrency: no overselling, no double-spent coupons, no duplicate
orders from a retried checkout, and no double-issued milestone rewards.

See [DECISIONS.md](DECISIONS.md) for the full design rationale, ambiguity resolutions,
and what's implemented vs. deferred.

See [examples.http](examples.http) for a runnable, narrated walkthrough of every
endpoint and every error code the API returns.

## Quickstart (from a clean clone)

**Backend** (Python 3.11+):

```bash
cd backend
python -m venv .venv
.venv/Scripts/activate       # Windows; `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

**Frontend** (Node 18+), in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The backend serves on http://localhost:8000 with CORS
already configured for the frontend's default origin.

## Tests

```bash
cd backend
pytest -q
```

42 tests covering unit logic (money rounding), every integration path listed in the
spec (cart CRUD, checkout, coupons, admin report), and four required concurrency
scenarios run with real parallel threads: oversell prevention, coupon double-redemption,
duplicate-checkout retry (with and without an `Idempotency-Key`), and double coupon
generation. Each concurrency test asserts on final DB state, not just response codes.

## API examples

[`examples.http`](examples.http) is a single continuous, runnable script covering the
happy path, every error code in `backend/app/errors.py`, both idempotency layers, and
the full admin milestone/coupon/report flow — each request has a one-line comment
explaining which invariant or error case it demonstrates. Every response in it was
captured from a real run against the seeded backend before being committed, not
hand-typed.

To run it:

- **VS Code:** install the [REST Client](https://marketplace.visualstudio.com/items?itemName=humao.rest-client)
  extension, open the file, and click "Send Request" above each block in order (top to
  bottom — later requests depend on state created by earlier ones). It uses that
  extension's `# @name` / `{{name.response.body.$.field}}` syntax to chain values
  (cart ids, order ids, the generated coupon code) between requests automatically.
- **JetBrains IDEs:** the built-in HTTP Client understands the same `.http` format and
  chaining syntax natively.
- **Anything else (curl, Postman, etc.):** read each request top to bottom and copy the
  relevant id/code from the previous response into the next one — the comments make the
  intent of each step clear even without automatic chaining.

Start from a freshly seeded backend before running it (`rm -f backend/app.db* && python
-m app.seed` from `backend/`), since several steps depend on an exact starting order
count to demonstrate the milestone logic correctly.

## Repository layout

```
backend/    FastAPI + SQLAlchemy + SQLite service (see backend/README.md)
frontend/   Vite + React + Tailwind UI (see frontend/README.md)
DECISIONS.md       design rationale, ambiguities, deferred work
examples.http      runnable API walkthrough covering every endpoint and error code
openapi.json       exported OpenAPI 3.1 schema (backend/openapi.json also works via /docs)
```

## Config

Copy `.env.example` to `.env` (or export the vars directly) to change the milestone
interval (`N`), discount percent (`X`), DB location, or allowed CORS origins.
