"""Container entrypoint: ensure DuckDB exists, then exec main command."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/app")
DB = ROOT / "data" / "sandbox.duckdb"
RAW = ROOT / "data" / "olist_raw" / "olist_orders_dataset.csv"


def main() -> None:
    os.chdir(ROOT)
    if not os.environ.get("OPENROUTER_API_KEY"):
        print("WARNING: OPENROUTER_API_KEY is not set. /ready will fail until it is.")

    if not DB.exists():
        if RAW.exists():
            print("Building sandbox.duckdb from olist_raw...")
            subprocess.check_call([sys.executable, "src/sandbox/build_db.py"])
        else:
            print("WARNING: data/sandbox.duckdb missing and olist_raw not found.")
            print("Mount data/ with sandbox.duckdb or CSVs before serving traffic.")
    else:
        print("Using existing data/sandbox.duckdb")

    if len(sys.argv) < 2:
        print("No command provided", file=sys.stderr)
        sys.exit(1)
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
