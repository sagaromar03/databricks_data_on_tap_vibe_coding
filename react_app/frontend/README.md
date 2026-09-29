# Data on Tap — React frontend

Vite + React + TypeScript. The second frontend on the shared backend; it calls
`backend/api.py` (FastAPI) over HTTP.

## Run standalone (mock data — no backend needed)

```
npm install
npm run dev            # http://localhost:5173
```

Mock mode is the default: `src/api.ts` returns sample data, so the whole UI
(all three roles) works without a backend or database. Good for local UI work.

Demo logins: customer `anna@example.se` / `pizza`; kitchen
`kitchen.goteborg@dataontap.se` / `kitchen`; partner `nils@dataontap.se` / `partner`.

## Run against the live API (real Lakebase data)

You need Databricks auth locally (so the backend can reach the Lakebase project)
and Python deps installed (`pip install -r ../../requirements.txt`).

```
# terminal 1 — the API (connects to Lakebase, port 8000)
cd ../..                      # repo root
uvicorn backend.api:app --port 8000 --reload

# terminal 2 — the React app, mock OFF (Vite proxies /api -> :8000)
cd react_app/frontend
VITE_USE_MOCK=false npm run dev
```

Now the app shows real branches/menu/stock, real login, and writes real orders
to Lakebase — the same data the Streamlit app uses.

## Build (for deploying alongside the API)

```
npm run build         # outputs static files to dist/
```

Serve `dist/` from the FastAPI app (or a Databricks App running uvicorn) to ship
one app that serves both the React bundle and `/api/*`.
