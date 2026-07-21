"""
Sprint 3 burst-load helper — run N concurrent questions and report p50/p95 latency.

Usage:
  python src/eval/burst_load.py
  python src/eval/burst_load.py --workers 10 --repeat 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.cache import question_cache, llm_cache
from pipeline import answer_questions_concurrent

DEFAULT_QUESTIONS = [
    "How many unique customers do we have?",
    "How many orders were delivered?",
    "What is the average review score?",
    "How many sellers are there?",
    "Which product category has the most items?",
    "How many orders were canceled?",
    "What payment types exist?",
    "How many products are in the catalog?",
    "Count orders placed in 2018",
    "How many order items are there?",
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--repeat", type=int, default=1, help="repeat question list N times")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    questions = DEFAULT_QUESTIONS * args.repeat
    if args.no_cache:
        question_cache.clear()
        llm_cache.clear()

    print(f"Running {len(questions)} questions with max_workers={args.workers}...")
    t0 = time.time()
    results = answer_questions_concurrent(questions, max_workers=args.workers)
    wall = time.time() - t0

    latencies = [r.get("latency_seconds") or 0 for r in results if r]
    costs = [r.get("total_cost") or 0 for r in results if r]
    statuses = {}
    for r in results:
        if not r:
            continue
        statuses[r.get("status", "unknown")] = statuses.get(r.get("status", "unknown"), 0) + 1

    report = {
        "n": len(questions),
        "workers": args.workers,
        "wall_clock_seconds": wall,
        "p50_latency_s": percentile(latencies, 0.50),
        "p95_latency_s": percentile(latencies, 0.95),
        "max_latency_s": max(latencies) if latencies else 0,
        "total_cost_usd": sum(costs),
        "status_counts": statuses,
        "cache_stats": question_cache.stats(),
        "guardrail_note": (
            "PRD guardrail is p95 under 20 concurrent requests. "
            "Use --workers 20 when budget allows."
        ),
    }
    print(json.dumps(report, indent=2))
    out = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "sprint3", "burst_load_results.json"
    )
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
