# Structured Products Pricer

Production-grade pricer for Autocallable structured products with Monte Carlo simulation, Brownian bridge barrier monitoring, and comprehensive Greeks calculation.

## ✨ Features

- **Multi-Asset Pricing**: Worst-of autocalls with correlated underlyings
- **Advanced Barriers**: Continuous knock-in monitoring via Brownian bridge
- **Comprehensive Greeks**: Delta, Vega, Rho with Common Random Numbers
- **Flexible Vol Models**: Flat, piecewise constant, and local stochastic volatility
- **Production Ready**: Type-safe, tested, and optimized for performance

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for UI)

### Installation

```bash
# 1. Install backend
pip install -e ./backend

# 2. Install API dependencies
pip install -e ./api

# 3. Install UI dependencies
cd ui && npm install
```

### Running Locally

```bash
# Terminal 1: Start API server
cd api
uvicorn main:app --reload --port 8000

# Terminal 2: Start UI
cd ui
npm run dev
```

Then open:
- **UI**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs

### Using Docker Compose

```bash
docker-compose up
```

## 📚 Documentation

- **[Development Setup](docs/development/setup.md)** - Detailed installation and configuration
- **[Architecture Overview](docs/architecture/overview.md)** - System design and components
- **[API Documentation](docs/api/endpoints.md)** - Endpoint reference
- **[All Documentation](docs/README.md)** - Complete documentation index

## 🧪 Testing

```bash
cd backend
pytest tests/ -v --cov=pricer
```

## 📦 Project Structure

```
pricer/
├── backend/          # Python pricing library
│   ├── src/pricer/   # Core modules (engines, pricers, risk)
│   ├── tests/        # Test suite
│   └── examples/     # CLI examples
├── api/              # FastAPI REST API
│   └── main.py       # API endpoints
├── ui/               # Next.js web interface
│   └── src/          # React components
└── docs/             # Documentation
```

## 🔧 Development

```bash
# Run tests
make test

# Type checking
make lint

# Format code
make format
```

See [Development Setup](docs/development/setup.md) for detailed instructions.

## 📖 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/schema` | Example term sheet |
| POST | `/price` | Price a product |
| POST | `/risk` | Risk analysis with Greeks |
| POST | `/vanilla/price` | Price vanilla options |
| GET | `/market-data` | Fetch market data |

## 🌐 Deployment

- **API**: Deploy to Render using `render.yaml`
- **UI**: Deploy to Vercel (auto-detected)
- **Production**: https://pricer-six.vercel.app

## 📄 License

MIT

## 🤝 Contributing

Contributions welcome! Please see [Development Setup](docs/development/setup.md) for getting started.

