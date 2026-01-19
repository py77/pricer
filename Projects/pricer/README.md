# Structured Products Pricer

Production-grade pricer for Autocallable structured products with web UI.

## Project Structure

```
pricer/
├── backend/          # Python pricer library (Monte Carlo, Greeks)
│   ├── src/pricer/   # Core pricing modules
│   ├── tests/        # Test suite
│   └── examples/     # CLI examples
├── api/              # FastAPI wrapper
│   └── main.py       # REST API endpoints
├── ui/               # Next.js web interface
│   └── src/          # React components
└── docker-compose.yml
```

## Quick Start

### Option 1: Manual Setup

```bash
# 1. Install backend
pip install -e ./backend

# 2. Install API dependencies
pip install fastapi uvicorn[standard]

# 3. Start API server
cd api
uvicorn main:app --reload --port 8000

# 4. In another terminal, start UI
cd ui
npm install
npm run dev
```

Open http://localhost:3000

### Option 2: Docker Compose

```bash
docker-compose up
```

- API: http://localhost:8000
- UI: http://localhost:3000
- API Docs: http://localhost:8000/docs

## Features

### Backend
- Multi-asset GBM with Cholesky correlation
- Brownian bridge continuous KI monitoring
- Coupon memory, autocall with stepping barriers
- Discrete and continuous dividends

### Risk
- Delta (1% spot bump)
- Vega (1 vol point bump)
- Rho (1bp rate bump)
- Common Random Numbers for stable Greeks

### UI
- Monaco JSON editor for term sheets
- Configurable paths, seed, bump sizes
- Summary cards, cashflow tables
- PV decomposition chart
- Greeks table

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/schema` | Get example term sheet |
| POST | `/price` | Price a product |
| POST | `/risk` | Risk analysis with Greeks |

## Testing

```bash
cd backend
python -m pytest tests/ -v
```

## Commands Reference

```bash
# Install backend
pip install -e ./backend

# Run API
cd api && uvicorn main:app --reload --port 8000

# Run UI
cd ui && npm run dev

# Run tests
cd backend && python -m pytest tests/ -v

# Generate TypeScript types
cd ui && npm run generate-types
```
