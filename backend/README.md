# Backend

FastAPI + SQLAlchemy 2.0 + SQLite (WAL mode). Python 3.11+.

## Setup

```bash
python -m venv .venv
.venv/Scripts/activate       # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
python -m app.seed           # creates app.db and seeds 6 products
uvicorn app.main:app --reload --port 8000
```

API docs: http://localhost:8000/docs
OpenAPI schema: http://localhost:8000/openapi.json

## Configuration

Environment variables (all optional, see `.env` example in the repo root):

| Var | Default | Meaning |
|---|---|---|
| `N` | `5` | Orders required per milestone |
| `X` | `10` | Discount percent awarded per milestone coupon |
| `DATABASE_URL` | `sqlite:///<backend>/app.db` | SQLAlchemy connection URL |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated allowed origins |

## Tests

```bash
pytest -q
```

42 tests: unit (money rounding), integration (carts, checkout, coupons, admin report),
and concurrency (`ThreadPoolExecutor`-driven races for oversell, double coupon
redemption, duplicate checkout retry, and double coupon generation). Each test gets
its own temp SQLite file — see `tests/conftest.py`.

## Lint / format

```bash
ruff check app tests
black app tests
```

## Project layout

```
app/
  main.py       # FastAPI app, CORS, router registration, lifespan (create_all)
  config.py     # env-driven settings (N, X, DATABASE_URL, CORS_ORIGINS)
  db.py         # engine, WAL pragma, commit-with-retry helper
  errors.py     # AppError hierarchy + error envelope + exception handlers
  money.py      # minor-unit formatting + ROUND_HALF_UP discount calculation
  models/       # SQLAlchemy ORM models (mirrors the DDL exactly)
  schemas/      # Pydantic request/response models
  routers/      # thin HTTP layer
  services/     # business logic + the checkout transaction
  seed.py       # seeds 6 products, one with inventory=3
tests/
```
