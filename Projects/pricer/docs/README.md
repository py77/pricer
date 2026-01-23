# Pricer Documentation

Welcome to the Structured Products Pricer documentation.

## Overview

The Pricer is a production-grade Python library for pricing autocallable structured products using Monte Carlo simulation with advanced features like Brownian bridge barrier monitoring, multi-asset correlation, and comprehensive Greeks calculation.

## Documentation Structure

### Getting Started
- [Development Setup](development/setup.md) - Environment setup and installation
- [Quick Start Guide](../README.md) - Get up and running quickly

### Architecture
- [System Overview](architecture/overview.md) - High-level architecture and component design
- [Pricing Engine](../backend/docs/pricing-engine.md) - Monte Carlo simulation details
- [Greeks Calculation](../backend/docs/greeks-calculation.md) - Risk sensitivity methodology
- [Brownian Bridge](../backend/docs/brownian-bridge.md) - Continuous barrier monitoring

### API Documentation
- [API Endpoints](api/endpoints.md) - Detailed endpoint documentation
- [Term Sheet Schema](api/schemas.md) - Product specification format
- [API Examples](api/examples.md) - Request/response examples

### Development
- [Testing Guide](development/testing.md) - Running and writing tests
- [Contributing](development/contributing.md) - Contribution guidelines
- [Code Style](development/code-style.md) - Coding standards

## Quick Links

- **API Documentation**: http://localhost:8000/docs (when running locally)
- **GitHub Repository**: [Your repo URL]
- **Issue Tracker**: [Your issues URL]

## Project Components

```
pricer/
├── backend/          # Core pricing library (Python)
├── api/              # FastAPI REST API
├── ui/               # Next.js web interface
└── docs/             # Documentation (you are here)
```

## Key Features

- **Multi-Asset Support**: Price products on baskets of underlyings with correlation
- **Advanced Barrier Monitoring**: Brownian bridge for continuous knock-in barriers
- **Comprehensive Greeks**: Delta, Vega, Rho with Common Random Numbers
- **Flexible Volatility Models**: Flat, piecewise constant, and local stochastic volatility
- **Production Ready**: Type-safe, tested, and optimized for performance
