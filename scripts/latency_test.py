"""
Latency test against a live Northstar base URL (local or AWS).

Examples:
  python scripts/latency_test.py --base-url http://127.0.0.1:8000
  python scripts/latency_test.py --base-url http://PUBLIC_IP:8000 --n 15 --concurrency 5
  python scripts/latency_test.py --base-url http://PUBLIC_IP:8000 --out docs/sprint4/aws_latency_results.json
"""
from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

QUESTIONS = [
    "How many unique customers do we have?",
    "How many orders have the status 'delivered'?",
    "Which product category has the most order items?",
    "How many distinct sellers are there?",
    "Why are sales down?",
    "Update the price of product X to $50.",
]


def percentile(vals: list[float], p: float) -> float:
    if not vals:
        return 0.0
    s = sorted(vals)
    k = (len(s) - 1) * p
    f = int(k)
    c = min(f + 1, len(s) - 1)
    if f == c:
        return s[f]
    return s[f] + (s[c] - s[f]) * (k - f)


def ask(base_url: str, question: str, timeout: float = 120.0) -> dict:
    url = base_url.rstrip("/") + "/ask"
    body = json.dumps({"question": question, "use_cache": False}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            wall = time.perf_counter() - t0
            return {
                "ok": True,
                "question": question,
                "status": data.get("status"),
                "latency_reported": data.get("latency_seconds"),
                "latency_wall": wall,
                "cost_usd": data.get("cost_usd"),
                "error": None,
            }
    except Exception as e:
        wall = time.perf_counter() - t0
        return {
            "ok": False,
            "question": question,
            "status": "error",
            "latency_reported": None,
            "latency_wall": wall,
            "cost_usd": None,
            "error": str(e),
        }


def check_ready(base_url: str) -> dict:
    url = base_url.rstrip("/") + "/ready"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return {"ok": resp.status == 200, "body": resp.read().decode("utf-8")[:500]}
    except Exception as e:
        return {"ok": False, "body": str(e)}


def run_sequential(base_url: str, n: int) -> list[dict]:
    rows = []
    for i in range(n):
        q = QUESTIONS[i % len(QUESTIONS)]
        print(f"  [seq {i+1}/{n}] {q[:50]}...")
        rows.append(ask(base_url, q))
    return rows


def run_concurrent(base_url: str, n: int, workers: int) -> list[dict]:
    questions = [QUESTIONS[i % len(QUESTIONS)] for i in range(n)]
    rows: list[dict | None] = [None] * n
    print(f"  [concurrent n={n} workers={workers}]")
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {pool.submit(ask, base_url, q): i for i, q in enumerate(questions)}
        for fut in as_completed(futs):
            i = futs[fut]
            rows[i] = fut.result()
    return [r for r in rows if r is not None]


def summarize(rows: list[dict], label: str) -> dict:
    walls = [r["latency_wall"] for r in rows if r.get("latency_wall") is not None]
    ok = sum(1 for r in rows if r.get("ok"))
    return {
        "label": label,
        "n": len(rows),
        "ok": ok,
        "errors": len(rows) - ok,
        "p50_wall_s": percentile(walls, 0.50),
        "p95_wall_s": percentile(walls, 0.95),
        "mean_wall_s": statistics.mean(walls) if walls else 0.0,
        "max_wall_s": max(walls) if walls else 0.0,
        "total_cost_usd": sum((r.get("cost_usd") or 0) for r in rows),
        "status_counts": _counts(rows),
    }


def _counts(rows: list[dict]) -> dict:
    c: dict[str, int] = {}
    for r in rows:
        k = r.get("status") or "unknown"
        c[k] = c.get(k, 0) + 1
    return c


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", required=True, help="e.g. http://127.0.0.1:8000 or http://EC2_IP:8000")
    ap.add_argument("--n", type=int, default=12, help="sequential requests")
    ap.add_argument("--concurrency", type=int, default=5, help="concurrent workers (0=skip)")
    ap.add_argument("--concurrent-n", type=int, default=10, help="total concurrent requests")
    ap.add_argument(
        "--out",
        default="",
        help="JSON output path (default docs/sprint4/aws_latency_results.json if under repo)",
    )
    args = ap.parse_args()

    base = args.base_url.rstrip("/")
    print(f"Target: {base}")
    ready = check_ready(base)
    print(f"Ready: {ready}")
    if not ready.get("ok"):
        print("ERROR: /ready failed — fix deploy before latency test")
        raise SystemExit(1)

    seq = run_sequential(base, args.n)
    seq_sum = summarize(seq, "sequential")
    print(json.dumps(seq_sum, indent=2))

    conc_sum = None
    conc_rows: list[dict] = []
    if args.concurrency and args.concurrency > 0:
        conc_rows = run_concurrent(base, args.concurrent_n, args.concurrency)
        conc_sum = summarize(conc_rows, f"concurrent_w{args.concurrency}")
        print(json.dumps(conc_sum, indent=2))

    report = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": base,
        "ready": ready,
        "sequential": seq_sum,
        "concurrent": conc_sum,
        "sequential_rows": seq,
        "concurrent_rows": conc_rows,
    }

    out = args.out
    if not out:
        root = Path(__file__).resolve().parents[1]
        out_path = root / "docs" / "sprint4" / "aws_latency_results.json"
    else:
        out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
