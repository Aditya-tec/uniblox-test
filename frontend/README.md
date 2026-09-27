# Frontend

Vite + React + Tailwind CSS. Talks to the backend via `fetch`.

## Setup

```bash
npm install
cp .env.example .env   # defaults to http://localhost:8000
npm run dev
```

Opens on http://localhost:5173. The backend must be running (see `../backend/README.md`)
and its `CORS_ORIGINS` must include this origin (it does, by default).

## Structure

- `src/api.js` — thin fetch wrapper; every backend error becomes an `ApiError { code, message, details }`.
- `src/errors.js` — maps each API error `code` to a human-readable message.
- `src/hooks/useCart.js` — cart state + `localStorage` persistence of the cart id.
- `src/components/` — `Catalog`, `CartView`, `CheckoutView`, `OrderConfirmation`, `AdminDashboard`.

The frontend never computes totals or inventory itself — it always displays what the API
returns, so it stays honest about being a thin view over backend truth.

## Scripts

- `npm run dev` — dev server
- `npm run build` — production build
- `npm run lint` — oxlint
