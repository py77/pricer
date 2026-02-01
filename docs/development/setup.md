# Development Setup Guide

This guide will help you set up your development environment for the Pricer project.

## Prerequisites

### Required Software

- **Python 3.11 or higher** ([Download](https://www.python.org/downloads/))
- **Node.js 18 or higher** ([Download](https://nodejs.org/))
- **Git** ([Download](https://git-scm.com/downloads))

### Recommended Tools

- **VS Code** with Python and TypeScript extensions
- **Docker Desktop** (optional, for containerized development)
- **Make** (optional, for using Makefile commands)

## Initial Setup

### 1. Clone the Repository

```bash
git clone <your-repo-url>
cd pricer
```

### 2. Set Up Python Environment

We recommend using a virtual environment to isolate dependencies:

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Upgrade pip
pip install --upgrade pip
```

### 3. Install Backend

Install the backend library in editable mode with development dependencies:

```bash
pip install -e ./backend[dev]
```

This installs:
- Core dependencies: numpy, scipy, pydantic, pandas
- Dev dependencies: pytest, pytest-cov, mypy, ruff

### 4. Install API

Install the API server dependencies:

```bash
pip install -e ./api
```

This installs:
- FastAPI and Uvicorn
- Backend library (from step 3)

### 5. Install UI

Install the Next.js UI dependencies:

```bash
cd ui
npm install
cd ..
```

### 6. Install Development Tools

Install pre-commit hooks for code quality:

```bash
pip install pre-commit
pre-commit install
```

## Verify Installation

### Test Backend

```bash
cd backend
pytest tests/ -v
```

Expected output: All tests should pass.

### Test Type Checking

```bash
cd backend
mypy src/pricer
```

Expected output: No type errors.

### Test Linting

```bash
cd backend
ruff check .
```

Expected output: No linting errors.

### Start API Server

```bash
cd api
uvicorn main:app --reload --port 8000
```

Then visit http://localhost:8000/docs to see the Swagger UI.

### Start UI

```bash
cd ui
npm run dev
```

Then visit http://localhost:3000 to see the web interface.

## Development Workflow

### Running Tests

```bash
# All backend tests
cd backend && pytest tests/ -v

# With coverage
cd backend && pytest tests/ -v --cov=pricer --cov-report=term-missing

# Specific test file
cd backend && pytest tests/test_greeks.py -v

# Specific test function
cd backend && pytest tests/test_greeks.py::test_delta_sensitivity -v
```

### Type Checking

```bash
# Check all files
cd backend && mypy src/pricer

# Check specific file
cd backend && mypy src/pricer/engines/path_generator.py
```

### Linting and Formatting

```bash
# Check for issues
cd backend && ruff check .

# Auto-fix issues
cd backend && ruff check . --fix

# Format code
cd backend && ruff format .
```

### Using Make Commands

If you have Make installed, you can use convenient shortcuts:

```bash
# Install all dependencies
make install

# Run all tests
make test

# Run linting
make lint

# Format code
make format

# Clean cache files
make clean

# Start API server
make dev-api

# Start UI server
make dev-ui
```

## IDE Setup

### VS Code

The project includes VS Code configuration in `.vscode/`:

- **settings.json**: Python interpreter, linting, formatting settings
- **launch.json**: Debug configurations for API and tests

**Recommended Extensions**:
- Python (ms-python.python)
- Pylance (ms-python.vscode-pylance)
- Ruff (charliermarsh.ruff)
- ESLint (dbaeumer.vscode-eslint)
- Prettier (esbenp.prettier-vscode)

### PyCharm

1. Open the project root directory
2. Configure Python interpreter: Settings → Project → Python Interpreter → Add → Existing environment → Select `.venv/bin/python`
3. Mark `backend/src` as Sources Root
4. Enable pytest: Settings → Tools → Python Integrated Tools → Testing → pytest

## Docker Development (Optional)

### Using Docker Compose

```bash
# Start all services
docker-compose up

# Start in background
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

Services:
- API: http://localhost:8000
- UI: http://localhost:3000

### Building Individual Containers

```bash
# Build API
cd api
docker build -t pricer-api .

# Run API
docker run -p 8000:8000 pricer-api
```

## Common Issues

### Python Not Found

**Windows**: If you get "Python was not found", you may need to:
1. Install Python from Microsoft Store, OR
2. Disable the app execution alias: Settings → Apps → Advanced app settings → App execution aliases → Turn off Python aliases

**Solution**: Use `python3` instead of `python`, or add Python to your PATH.

### Import Errors

If you get import errors like `ModuleNotFoundError: No module named 'pricer'`:

1. Ensure you've installed the backend: `pip install -e ./backend`
2. Activate your virtual environment
3. Check your PYTHONPATH includes the backend src directory

### Port Already in Use

If port 8000 or 3000 is already in use:

```bash
# Find process using port (Windows)
netstat -ano | findstr :8000

# Find process using port (macOS/Linux)
lsof -i :8000

# Kill the process or use a different port
uvicorn main:app --reload --port 8001
```

### Pre-commit Hook Failures

If pre-commit hooks fail:

```bash
# Run manually to see errors
pre-commit run --all-files

# Fix formatting issues
cd backend && ruff format .

# Fix linting issues
cd backend && ruff check . --fix

# Update hooks
pre-commit autoupdate
```

### Type Checking Errors

If mypy reports errors:

1. Ensure you have the latest type stubs: `pip install types-all`
2. Check your mypy configuration in `backend/pyproject.toml`
3. Some third-party libraries may not have type stubs - you can ignore them in mypy config

## Environment Variables

The project currently doesn't require environment variables for local development. If you need to configure:

### API Configuration

Create `api/.env`:
```env
# Optional: Override default settings
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
```

### UI Configuration

Create `ui/.env.local`:
```env
# API endpoint
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## Next Steps

Once your environment is set up:

1. **Explore the codebase**: Start with `backend/src/pricer/products/schema.py` to understand term sheets
2. **Run examples**: Check `backend/examples/` for CLI usage examples
3. **Try the API**: Use the Swagger UI at http://localhost:8000/docs
4. **Read the docs**: See `docs/architecture/overview.md` for system architecture
5. **Write tests**: Follow the patterns in `backend/tests/`

## Getting Help

- **Documentation**: See `docs/` directory
- **API Docs**: http://localhost:8000/docs (when running)
- **Issues**: [Your issue tracker URL]
- **Discussions**: [Your discussions URL]

## Contributing

Before contributing, please:

1. Read the contribution guidelines (coming soon)
2. Ensure all tests pass
3. Run linting and type checking
4. Write tests for new features
5. Update documentation as needed

Happy coding! 🚀
