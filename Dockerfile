FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/pyproject.toml backend/
COPY backend/src backend/src
COPY backend/examples backend/examples
RUN pip install --no-cache-dir -e ./backend

COPY api/ api/

CMD uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}
