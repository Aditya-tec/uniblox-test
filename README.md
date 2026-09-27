# Reliable Checkout & Rewards Service

A small e-commerce checkout API (FastAPI + SQLite) plus a React frontend, built around
correctness under concurrency: no overselling, no double-spent coupons, no duplicate
orders from a retried checkout, and no double-issued milestone rewards.

See [DECISIONS.md](DECISIONS.md) for the full design rationale, ambiguity resolutions,
and what's implemented vs. deferred.

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

## Repository layout

```
backend/    FastAPI + SQLAlchemy + SQLite service (see backend/README.md)
frontend/   Vite + React + Tailwind UI (see frontend/README.md)
DECISIONS.md       design rationale, ambiguities, deferred work
openapi.json       exported OpenAPI 3.1 schema (backend/openapi.json also works via /docs)
```

## Config

Copy `.env.example` to `.env` (or export the vars directly) to change the milestone
interval (`N`), discount percent (`X`), DB location, or allowed CORS origins.
