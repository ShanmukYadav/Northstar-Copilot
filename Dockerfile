# Northstar Insight Copilot — production-ish pilot image
FROM python:3.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# System deps (duckdb wheels usually enough; curl for healthchecks)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# App code (data mounted or copied separately — see compose)
COPY src/ ./src/
COPY evals/ ./evals/
COPY scripts/ ./scripts/
COPY docs/ ./docs/
COPY ops/ ./ops/
COPY README.md ./

# Default: expect data/sandbox.duckdb via volume; optional entrypoint builds if CSVs present
COPY docker/entrypoint.py /entrypoint.py

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
  CMD curl -fsS http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["python", "/entrypoint.py"]
CMD ["uvicorn", "src.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
