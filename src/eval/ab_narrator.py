"""
Sprint 3 A/B: Narrator cheap path (Haiku / task=narrator) vs strong (Sonnet / narrator_strong).

Runs a small fixed question set through the full pipeline twice and reports
latency, cost, and answer length. Faithfulness scoring (RAGAS) is Stage 7 —
this harness is the cost/quality signal pair for routing policy decisions.

Usage (from repo root, with OPENROUTER_API_KEY set):
  python src/eval/ab_narrator.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.cache import question_cache, llm_cache
from gateway.client import reset_cost_summary, get_cost_summary
from pipeline import answer_question

# Small, cheap set — expand once budget allows
AB_QUESTIONS = [
    "How many unique customers do we have?",
    "How many orders were delivered?",
    "Which payment type is used most often?",
]


def run_arm(strong: bool) -> list[dict]:
    question_cache.clear()
    llm_cache.clear()
    reset_cost_summary()
    rows = []
    for q in AB_QUESTIONS:
        # Disable question cache so both arms actually run narration
        result = answer_question(q, use_question_cache=False, narrator_strong=strong)
        rows.append(
            {
                "question": q,
                "status": result.get("status"),
                "latency_seconds": result.get("latency_seconds"),
                "cost_usd": result.get("total_cost"),
                "answer_len": len(result.get("final_answer") or ""),
                "confidence": result.get("confidence"),
                "model_hint": "narrator_strong" if strong else "narrator",
            }
        )
    summary = get_cost_summary()
    return rows, summary


def main():
    print("=== A/B Narrator: cheap (Haiku) ===")
    cheap_rows, cheap_sum = run_arm(False)
    print(json.dumps(cheap_rows, indent=2))

    print("\n=== A/B Narrator: strong (Sonnet) ===")
    strong_rows, strong_sum = run_arm(True)
    print(json.dumps(strong_rows, indent=2))

    def avg(rows, key):
        vals = [r[key] for r in rows if r.get(key) is not None]
        return sum(vals) / len(vals) if vals else 0.0

    report = {
        "cheap": {
            "avg_latency_s": avg(cheap_rows, "latency_seconds"),
            "avg_cost_usd": avg(cheap_rows, "cost_usd"),
            "gateway_total": cheap_sum["total_cost_usd"],
            "answered": sum(1 for r in cheap_rows if r["status"] == "answered"),
        },
        "strong": {
            "avg_latency_s": avg(strong_rows, "latency_seconds"),
            "avg_cost_usd": avg(strong_rows, "cost_usd"),
            "gateway_total": strong_sum["total_cost_usd"],
            "answered": sum(1 for r in strong_rows if r["status"] == "answered"),
        },
        "note": (
            "Pick winner on cost+latency for default path; escalate to strong only "
            "when faithfulness eval (Stage 7 RAGAS) shows a material gap."
        ),
    }
    print("\n=== Summary ===")
    print(json.dumps(report, indent=2))

    out_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "sprint3", "ab_narrator_results.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"cheap_rows": cheap_rows, "strong_rows": strong_rows, "summary": report}, f, indent=2)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
