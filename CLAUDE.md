# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A structured products pricer: Monte Carlo simulation engine for autocallable notes with a FastAPI backend and Next.js frontend.

## Development Commands

### Backend
```bash
pip install -r requirements.txt
pip install -e ./backend              # Install pricer library as editable package

# Run all tests
cd backend && python -m pytest

# Run a single test file
cd backend && python -m pytest tests/test_pricing.py

# Run a specific test
cd backend && python -m pytest tests/test_pricing.py::test_name

# Start API server locally
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

### Frontend (ui/)
```bash
cd ui
npm install
npm run dev          # Dev server on localhost:3000
npm run build        # Production build
npm run generate-types  # Generate TypeScript types from OpenAPI schema (requires local API running)
```

### Linting (backend)
```bash
cd backend && ruff check src/    # Line length 100, target Python 3.11
```

## Architecture

### Two-Package Backend Structure

The backend has two separate Python packages:
- **`backend/`** — the `pricer` library (installed via `pip install -e ./backend`). Contains all pricing logic. Configured in `backend/pyproject.toml`.
- **`api/`** — the FastAPI wrapper that imports from `pricer`. Configured in `api/pyproject.toml`. Entry point: `api/main.py`.

On Cloud Run, the Dockerfile installs both: `pip install -r requirements.txt` then `pip install -e ./backend`.

### Pricing Pipeline

The core flow spans multiple files in `backend/src/pricer/`:

```
TermSheet (products/schema.py)
    → build_simulation_grid (engines/grid.py)
    → PathGenerator.generate (engines/path_generator.py)
    → EventEngine.evaluate (pricers/event_engine.py)
    → PricingResult
```

**AutocallPricer** (`pricers/autocall_pricer.py`) orchestrates this entire flow. `PricingConfig` controls num_paths, seed, antithetic, block_size.

### Key Engine Details

- **SimulationGrid** (`engines/grid.py`): Merges valuation, observation, ex-dividend, and maturity dates into a unified time grid with event type annotations.
- **PathGenerator** (`engines/path_generator.py`): Correlated GBM via Cholesky decomposition. Supports piecewise constant vol, discrete dividends as spot jumps, Brownian bridge for continuous barrier monitoring, and QE (Quadratic Exponential) scheme for Heston-style LSV.
- **EventEngine** (`pricers/event_engine.py`): At each observation date, evaluates in order: autocall check → coupon check → memory coupon update → maturity redemption (based on knock-in state).
- **Greeks** (`risk/greeks.py`): Finite difference bumping with Common Random Numbers (CRN) — same seed for base and bumped scenarios. Supports central and forward differences for delta, vega, rho. Controlled by `BumpingConfig`.

### Schema

`TermSheet` (Pydantic, `extra = "forbid"`) is the single input model for pricing. Key nested models: Meta, Underlying (with VolModel and DividendModel), DiscountCurve, Correlation, Schedule, Autocall, KnockIn, Coupon, Redemption.

### Frontend

Next.js 14 App Router with two pages:
- `/` — Pricing page
- `/risk` — Risk analysis with Monaco editor for term sheet JSON, Greeks table, PV decomposition

API client in `ui/src/api/client.ts` talks to the FastAPI backend. Base URL from `NEXT_PUBLIC_API_URL` env var, defaults to Cloud Run production URL.

## API Endpoints

- `GET /health` — Health check
- `GET /schema` — Example term sheet
- `POST /price` — Price a term sheet
- `POST /risk` — Compute Greeks
- `GET /market-data?tickers=AAPL,GOOG` — Fetch market data via yfinance
- `POST /vanilla/price` — Vanilla option pricing
- `POST /vanilla/implied-vol` — Implied volatility

CORS origins configured in `api/main.py`: localhost:3000, localhost:3001, pricer-six.vercel.app, *.vercel.app.

## Deployment

- **Frontend**: Vercel. Root Directory must be set to `ui` in Vercel project settings (not in vercel.json). Auto-deploys on push to `main`.
- **Backend**: Google Cloud Run (us-central1). Dockerfile at `api/Dockerfile`. Deploy with:
  ```bash
  gcloud run deploy pricer-api \
    --source . \
    --dockerfile api/Dockerfile \
    --region us-central1 \
    --allow-unauthenticated \
    --memory 1Gi \
    --timeout 120 \
    --min-instances 0 \
    --max-instances 3
  ```
  The Dockerfile installs all deps from `requirements.txt`, then installs the `pricer` package as editable. Cloud Run injects `$PORT` env var; the CMD uses shell form to expand it.

## UI Theme

Minimalist dark theme: background #0c0d10, teal accent #2dd4bf, DM Sans font, no gradients/glow.

## Gotchas

- `.gitignore` uses `/lib/` (not `lib/`) to only ignore root-level lib — `ui/src/lib/` must be tracked.
- Don't put `rootDirectory` in vercel.json — set it in Vercel project settings.
- `@/` path alias in tsconfig maps to `./src/*`.
- Cloud Run Dockerfile handles PYTHONPATH via `pip install -e ./backend`.
