#!/bin/sh
set -e
cd /app

# Load .env if mounted (docker compose)
if [ -f /app/.env ]; then
  set -a
  # shellcheck disable=SC1091
  . /app/.env
  set +a
fi

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "WARNING: OPENROUTER_API_KEY is not set. /ready will fail until it is."
fi

# Build DuckDB if missing and raw CSVs are present
if [ ! -f /app/data/sandbox.duckdb ]; then
  if [ -d /app/data/olist_raw ] && [ -f /app/data/olist_raw/olist_orders_dataset.csv ]; then
    echo "Building sandbox.duckdb from olist_raw..."
    python src/sandbox/build_db.py
  else
    echo "WARNING: data/sandbox.duckdb missing and olist_raw not found."
    echo "Mount data/ with sandbox.duckdb or CSVs before serving traffic."
  fi
else
  echo "Using existing data/sandbox.duckdb"
fi

exec "$@"
