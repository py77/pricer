# Pricer Project Refactoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Modernize and refactor the pricer project using new skills and best practices for improved maintainability, testability, and developer experience.

**Architecture:** Multi-phase refactoring focusing on code organization, documentation, type safety, testing infrastructure, and CI/CD setup without breaking existing functionality.

**Tech Stack:** Python 3.11+, FastAPI, Next.js, pytest, mypy, ruff, GitHub Actions

---

## User Review Required

> [!IMPORTANT]
> **Breaking Changes**: None expected - all refactoring maintains backward compatibility with existing API and term sheet schemas.

> [!WARNING]
> **Testing Requirements**: After each task, existing tests must pass. New tests will be added incrementally.

> [!CAUTION]
> **Python Environment**: The current environment doesn't have Python accessible via `python` command. You may need to use `python3` or configure the Python path before starting implementation.

---

## Proposed Changes

### Phase 1: Project Structure & Documentation

Establish proper project documentation structure and improve code organization.

#### [NEW] [docs/README.md](file:///c:/Users/longr/pricer/docs/README.md)

Create documentation index with links to architecture, API docs, and development guides.

#### [NEW] [docs/architecture/overview.md](file:///c:/Users/longr/pricer/docs/architecture/overview.md)

Document the overall system architecture including:
- Component diagram (backend, API, UI)
- Data flow for pricing and risk calculations
- Monte Carlo simulation architecture
- Brownian bridge implementation details

#### [NEW] [docs/development/setup.md](file:///c:/Users/longr/pricer/docs/development/setup.md)

Comprehensive development setup guide covering:
- Environment setup (Python, Node.js)
- Installation steps
- Running tests
- Local development workflow

#### [MODIFY] [README.md](file:///c:/Users/longr/pricer/README.md)

Simplify root README to essential quick-start info and link to detailed docs.

---

### Phase 2: Code Organization & Type Safety

Improve code organization and strengthen type safety across the codebase.

#### [MODIFY] [backend/src/pricer/__init__.py](file:///c:/Users/longr/pricer/backend/src/pricer/__init__.py)

Add comprehensive module-level exports with type hints for better IDE support:
```python
"""Structured Products Pricer - Production-grade pricing library."""

from pricer.products.schema import TermSheet
from pricer.pricers.autocall_pricer import AutocallPricer, PricingConfig
from pricer.risk.greeks import compute_greeks, BumpingConfig, GreeksResult

__version__ = "0.1.0"
__all__ = [
    "TermSheet",
    "AutocallPricer",
    "PricingConfig",
    "compute_greeks",
    "BumpingConfig",
    "GreeksResult",
]
```

#### [NEW] [backend/py.typed](file:///c:/Users/longr/pricer/backend/py.typed)

Add PEP 561 marker file to indicate the package supports type checking.

#### [MODIFY] [backend/pyproject.toml](file:///c:/Users/longr/pricer/backend/pyproject.toml)

Add package data configuration to include py.typed:
```toml
[tool.setuptools.package-data]
pricer = ["py.typed"]
```

---

### Phase 3: Testing Infrastructure

Enhance testing infrastructure with better coverage, fixtures, and test organization.

#### [NEW] [backend/tests/conftest.py](file:///c:/Users/longr/pricer/backend/tests/conftest.py)

Create shared pytest fixtures for common test data:
```python
"""Shared pytest fixtures for pricer tests."""

import pytest
from datetime import date, timedelta
from pricer.products.schema import (
    TermSheet, Meta, Underlying, DividendModel, VolModel,
    DividendModelType, VolModelType, DiscountCurve, Correlation,
    Schedule, Autocall, KnockIn, Coupon, Redemption,
    BarrierMonitoringType, SettlementType
)

@pytest.fixture
def sample_term_sheet():
    """Create a standard autocall term sheet for testing."""
    # Implementation here
    pass

@pytest.fixture
def multi_asset_term_sheet():
    """Create a multi-asset worst-of autocall for testing."""
    pass

@pytest.fixture
def pricing_config():
    """Standard pricing configuration."""
    pass
```

#### [NEW] [backend/tests/unit/](file:///c:/Users/longr/pricer/backend/tests/unit/)

Create unit test directory structure:
- `test_schema_validation.py` - Schema validation edge cases
- `test_day_count.py` - Day count convention tests (move from root)
- `test_calendar.py` - Calendar business day tests
- `test_correlation.py` - Correlation matrix validation

#### [NEW] [backend/tests/integration/](file:///c:/Users/longr/pricer/backend/tests/integration/)

Create integration test directory:
- `test_pricing_workflow.py` - End-to-end pricing tests
- `test_greeks_workflow.py` - End-to-end Greeks calculation
- `test_api_integration.py` - API endpoint integration tests

#### [MODIFY] Existing test files

Move existing tests to appropriate directories:
- `test_day_count.py` → `unit/test_day_count.py`
- `test_schema.py` → `unit/test_schema_validation.py`
- `test_autocallable_regression.py` → `integration/test_pricing_workflow.py`
- `test_greeks.py` → `integration/test_greeks_workflow.py`

---

### Phase 4: API Improvements

Refactor API for better maintainability and add proper error handling.

#### [NEW] [api/routers/](file:///c:/Users/longr/pricer/api/routers/)

Split monolithic `main.py` into router modules:
- `health.py` - Health check endpoint
- `pricing.py` - Pricing endpoints (/price, /schema)
- `risk.py` - Risk analysis endpoints (/risk)
- `vanilla.py` - Vanilla option endpoints
- `market_data.py` - Market data endpoints

#### [NEW] [api/models/](file:///c:/Users/longr/pricer/api/models/)

Extract Pydantic models from main.py:
- `requests.py` - Request models (PriceRequest, RiskRequest, etc.)
- `responses.py` - Response models (PriceResponse, RiskResponse, etc.)
- `config.py` - Configuration models (RunConfig, BumpConfig)

#### [NEW] [api/middleware/](file:///c:/Users/longr/pricer/api/middleware/)

Add middleware for:
- `error_handler.py` - Centralized error handling
- `logging.py` - Request/response logging
- `timing.py` - Request timing metrics

#### [MODIFY] [api/main.py](file:///c:/Users/longr/pricer/api/main.py)

Refactor to use routers:
```python
"""FastAPI application for structured products pricer."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import health, pricing, risk, vanilla, market_data
from api.middleware import error_handler, logging, timing

app = FastAPI(
    title="Structured Products Pricer API",
    description="API for pricing autocallable structured products with Greeks",
    version="1.0.0",
)

# Middleware
app.add_middleware(CORSMiddleware, ...)
app.add_middleware(timing.TimingMiddleware)
app.add_middleware(logging.LoggingMiddleware)
app.add_exception_handler(Exception, error_handler.global_exception_handler)

# Routers
app.include_router(health.router, tags=["health"])
app.include_router(pricing.router, tags=["pricing"])
app.include_router(risk.router, tags=["risk"])
app.include_router(vanilla.router, prefix="/vanilla", tags=["vanilla"])
app.include_router(market_data.router, prefix="/market-data", tags=["market-data"])
```

---

### Phase 5: Code Quality & Linting

Set up comprehensive code quality tools and pre-commit hooks.

#### [NEW] [.pre-commit-config.yaml](file:///c:/Users/longr/pricer/.pre-commit-config.yaml)

Configure pre-commit hooks:
```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files
      - id: check-json
      - id: check-toml

  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.1.14
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.8.0
    hooks:
      - id: mypy
        additional_dependencies: [numpy, scipy, pydantic, pandas]
        args: [--strict]
```

#### [NEW] [.github/workflows/ci.yml](file:///c:/Users/longr/pricer/.github/workflows/ci.yml)

GitHub Actions CI pipeline:
```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.11", "3.12"]
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -e ./backend[dev]
          pip install -e ./api
      
      - name: Run ruff
        run: cd backend && ruff check .
      
      - name: Run mypy
        run: cd backend && mypy src/pricer
      
      - name: Run tests
        run: cd backend && pytest tests/ -v --cov=pricer --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./backend/coverage.xml
```

#### [NEW] [.github/workflows/api-test.yml](file:///c:/Users/longr/pricer/.github/workflows/api-test.yml)

API integration testing workflow:
```yaml
name: API Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main, develop]

jobs:
  api-test:
    runs-on: ubuntu-latest
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      
      - name: Install dependencies
        run: |
          pip install -e ./backend
          pip install -e ./api
          pip install httpx pytest-asyncio
      
      - name: Run API tests
        run: cd api && pytest tests/ -v
```

---

### Phase 6: Performance & Monitoring

Add performance monitoring and optimization utilities.

#### [NEW] [backend/src/pricer/utils/profiling.py](file:///c:/Users/longr/pricer/backend/src/pricer/utils/profiling.py)

Performance profiling utilities:
```python
"""Performance profiling utilities."""

import time
import functools
import logging
from typing import Callable, Any

logger = logging.getLogger(__name__)

def profile_time(func: Callable) -> Callable:
    """Decorator to profile function execution time."""
    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        logger.info(f"{func.__name__} took {elapsed:.2f}ms")
        return result
    return wrapper
```

#### [NEW] [backend/src/pricer/utils/memory.py](file:///c:/Users/longr/pricer/backend/src/pricer/utils/memory.py)

Memory usage tracking utilities:
```python
"""Memory usage tracking utilities."""

import numpy as np
from typing import Dict, Any

def estimate_memory_usage(
    num_paths: int,
    num_steps: int,
    num_assets: int,
    dtype: np.dtype = np.float32
) -> Dict[str, Any]:
    """Estimate memory usage for Monte Carlo simulation."""
    bytes_per_element = np.dtype(dtype).itemsize
    
    # Spot paths: [num_paths, num_steps+1, num_assets]
    spots_mb = (num_paths * (num_steps + 1) * num_assets * bytes_per_element) / (1024**2)
    
    # Random numbers: [num_paths, num_steps, num_assets]
    randoms_mb = (num_paths * num_steps * num_assets * bytes_per_element) / (1024**2)
    
    total_mb = spots_mb + randoms_mb
    
    return {
        "spots_mb": spots_mb,
        "randoms_mb": randoms_mb,
        "total_mb": total_mb,
        "recommended_block_size": min(50_000, max(1_000, int(500 / total_mb * num_paths)))
    }
```

---

### Phase 7: Developer Experience

Improve developer experience with better tooling and documentation.

#### [NEW] [.vscode/settings.json](file:///c:/Users/longr/pricer/.vscode/settings.json)

VS Code workspace settings:
```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/bin/python",
  "python.testing.pytestEnabled": true,
  "python.testing.pytestArgs": ["backend/tests"],
  "python.linting.enabled": true,
  "python.linting.mypyEnabled": true,
  "python.formatting.provider": "none",
  "[python]": {
    "editor.defaultFormatter": "charliermarsh.ruff",
    "editor.formatOnSave": true,
    "editor.codeActionsOnSave": {
      "source.organizeImports": true,
      "source.fixAll": true
    }
  },
  "files.exclude": {
    "**/__pycache__": true,
    "**/*.pyc": true,
    "**/.pytest_cache": true,
    "**/.mypy_cache": true,
    "**/.ruff_cache": true
  }
}
```

#### [NEW] [.vscode/launch.json](file:///c:/Users/longr/pricer/.vscode/launch.json)

Debug configurations:
```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python: API Server",
      "type": "python",
      "request": "launch",
      "module": "uvicorn",
      "args": ["main:app", "--reload", "--port", "8000"],
      "cwd": "${workspaceFolder}/api",
      "env": {"PYTHONPATH": "${workspaceFolder}/backend/src"}
    },
    {
      "name": "Python: Current Test File",
      "type": "python",
      "request": "launch",
      "module": "pytest",
      "args": ["${file}", "-v"],
      "cwd": "${workspaceFolder}/backend"
    }
  ]
}
```

#### [NEW] [Makefile](file:///c:/Users/longr/pricer/Makefile)

Common development commands:
```makefile
.PHONY: install test lint format clean dev-api dev-ui

install:
	pip install -e ./backend[dev]
	pip install -e ./api
	cd ui && npm install

test:
	cd backend && pytest tests/ -v --cov=pricer

lint:
	cd backend && ruff check . && mypy src/pricer

format:
	cd backend && ruff format .

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

dev-api:
	cd api && uvicorn main:app --reload --port 8000

dev-ui:
	cd ui && npm run dev
```

---

### Phase 8: Documentation Generation

Set up automated documentation generation.

#### [NEW] [docs/api/](file:///c:/Users/longr/pricer/docs/api/)

API documentation structure:
- `endpoints.md` - Detailed endpoint documentation
- `schemas.md` - Term sheet schema documentation
- `examples.md` - Example requests and responses

#### [NEW] [backend/docs/](file:///c:/Users/longr/pricer/backend/docs/)

Backend documentation:
- `pricing-engine.md` - Monte Carlo pricing engine details
- `greeks-calculation.md` - Greeks computation methodology
- `brownian-bridge.md` - Brownian bridge implementation
- `correlation.md` - Correlation matrix handling

---

## Verification Plan

### Automated Tests

After each phase, run:
```bash
# Backend tests
cd backend && pytest tests/ -v --cov=pricer --cov-report=term-missing

# Type checking
cd backend && mypy src/pricer

# Linting
cd backend && ruff check .

# API tests (once API refactored)
cd api && pytest tests/ -v
```

### Manual Verification

1. **Phase 1-2**: Verify documentation is readable and links work
2. **Phase 3**: Ensure all existing tests still pass after reorganization
3. **Phase 4**: Test API endpoints manually via `/docs` Swagger UI
4. **Phase 5**: Verify pre-commit hooks work: `pre-commit run --all-files`
5. **Phase 6**: Run performance benchmarks on sample term sheets
6. **Phase 7**: Test VS Code debugging and development workflow
7. **Phase 8**: Review generated documentation for completeness

### Success Criteria

- [ ] All existing tests pass
- [ ] Type checking passes with no errors
- [ ] Linting passes with no errors
- [ ] API endpoints return expected responses
- [ ] Documentation is comprehensive and accurate
- [ ] CI/CD pipeline runs successfully
- [ ] Pre-commit hooks work correctly
- [ ] Development workflow is smooth and well-documented
