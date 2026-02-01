.PHONY: install test lint format clean dev-api dev-ui help

help:
	@echo "Available commands:"
	@echo "  make install    - Install all dependencies"
	@echo "  make test       - Run all tests with coverage"
	@echo "  make lint       - Run linting and type checking"
	@echo "  make format     - Format code with ruff"
	@echo "  make clean      - Remove cache files"
	@echo "  make dev-api    - Start API development server"
	@echo "  make dev-ui     - Start UI development server"

install:
	pip install --upgrade pip
	pip install -e ./backend[dev]
	pip install -e ./api
	cd ui && npm install
	pip install pre-commit
	pre-commit install

test:
	cd backend && pytest tests/ -v --cov=pricer --cov-report=term-missing

lint:
	cd backend && ruff check src/ tests/
	cd backend && mypy src/pricer

format:
	cd backend && ruff format src/ tests/

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

dev-api:
	cd api && uvicorn main:app --reload --port 8000

dev-ui:
	cd ui && npm run dev
