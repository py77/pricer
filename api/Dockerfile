FROM python:3.11-slim

WORKDIR /app

# Install backend
COPY backend/pyproject.toml backend/
COPY backend/src backend/src
RUN pip install --no-cache-dir -e ./backend

# Install API deps
RUN pip install --no-cache-dir fastapi uvicorn[standard]

# Copy API
COPY api/ api/

EXPOSE 8000
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
