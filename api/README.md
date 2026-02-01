# Pricer API

FastAPI wrapper for the structured products pricer backend.

## Installation

```bash
# Install backend as editable package first
pip install -e ../backend

# Install API dependencies
pip install -e .
```

## Running

```bash
# Development server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Or directly
python main.py
```

## Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/schema` | Get example term sheet |
| POST | `/price` | Price a structured product |
| POST | `/risk` | Run risk analysis with Greeks |

## Example Requests

### Health Check
```bash
curl http://localhost:8000/health
```

### Get Example Schema
```bash
curl http://localhost:8000/schema
```

### Price a Product
```bash
curl -X POST http://localhost:8000/price \
  -H "Content-Type: application/json" \
  -d '{
    "term_sheet": {...},
    "run_config": {
      "paths": 100000,
      "seed": 42,
      "block_size": 50000
    }
  }'
```

### Risk Analysis
```bash
curl -X POST http://localhost:8000/risk \
  -H "Content-Type: application/json" \
  -d '{
    "term_sheet": {...},
    "run_config": {"paths": 100000, "seed": 42},
    "bump_config": {"spot_bump": 0.01, "vol_bump": 0.01, "include_rho": false}
  }'
```

## OpenAPI Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc
- OpenAPI JSON: http://localhost:8000/openapi.json
