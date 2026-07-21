"""
Sprint 3 DSPy scaffold for Query Writer prompt optimization.

Full DSPy compile loops need a metric over the golden set and a model budget.
This module:

1. Documents the intended DSPy signature and metric (execution accuracy).
2. Runs a *manual* prompt-variant A/B (baseline vs. "rules-first" system prompt)
   without requiring DSPy installed — so the sprint still produces a before/after
   number when OPENROUTER_API_KEY is set.
3. If `dspy` is installed, exposes `build_dspy_module()` for a real compile pass.

Usage:
  python src/eval/dspy_query_writer_stub.py
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sandbox"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verifier"))

from gateway.client import complete, reset_cost_summary
from build_db import get_readonly_connection
from checks import verify
from result_match import results_match, execute_sql_rows

GOLDEN_SET_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "evals", "golden_set", "golden_set_v1.json"
)

BASELINE_RULES = """You write DuckDB SELECT SQL for Olist e-commerce.
Return ONLY JSON: {"sql": "...", "cannot_answer": false}
Use COUNT(DISTINCT order_id) when joining order_items. Use customer_unique_id for unique customers.
"""

RULES_FIRST = """You write DuckDB SELECT SQL for Olist e-commerce.

HARD RULES (check before writing SQL):
1. Join orders↔order_items is 1:N → COUNT(DISTINCT order_id) for order counts.
2. Unique customers → COUNT(DISTINCT customer_unique_id), never customer_id alone.
3. Date diffs → DATE_DIFF('day', start, end). Never CAST(interval AS INTEGER).
4. SELECT only. No invented columns.

Return ONLY JSON: {"sql": "...", "cannot_answer": false}
"""


def _parse_sql(raw: str) -> str | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    try:
        obj = json.loads(text)
        return obj.get("sql")
    except json.JSONDecodeError:
        return None


def _gold_rows(sql: str):
    con = get_readonly_connection()
    try:
        return execute_sql_rows(con, sql)
    finally:
        con.close()


def eval_prompt_variant(system_prompt: str, items: list[dict], label: str) -> dict:
    reset_cost_summary()
    n = 0
    correct = 0
    for item in items:
        if not item.get("gold_sql"):
            continue
        n += 1
        gw = complete(
            "query_writer",
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": item["question"]},
            ],
            use_cache=False,
        )
        sql = _parse_sql(gw["content"])
        if not sql:
            continue
        v = verify(sql)
        if v.status != "pass":
            continue
        got = _gold_rows(sql)
        gold = _gold_rows(item["gold_sql"])
        if got is not None and gold is not None and results_match(gold, got):
            correct += 1
    return {
        "label": label,
        "n_executable": n,
        "correct": correct,
        "accuracy": (correct / n) if n else 0.0,
    }


def build_dspy_module():
    """Optional real DSPy module when the package is installed."""
    try:
        import dspy
    except ImportError as e:
        raise ImportError(
            "dspy is not installed. pip install dspy-ai  — or use the manual A/B path."
        ) from e

    class WriteSQL(dspy.Signature):
        """Write a correct DuckDB SELECT for an Olist business question."""
        question: str = dspy.InputField()
        sql: str = dspy.OutputField(desc="Single DuckDB SELECT statement")

    class QueryWriterModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.generate = dspy.ChainOfThought(WriteSQL)

        def forward(self, question: str):
            return self.generate(question=question)

    return QueryWriterModule()


def main():
    with open(GOLDEN_SET_PATH, encoding="utf-8") as f:
        golden = json.load(f)
    # Cap to keep cost low for a first Sprint 3 pass
    sample = [g for g in golden if g.get("gold_sql")][:8]

    print(f"Evaluating prompt variants on {len(sample)} golden items with gold_sql...")
    baseline = eval_prompt_variant(BASELINE_RULES, sample, "baseline_short")
    rules_first = eval_prompt_variant(RULES_FIRST, sample, "rules_first")

    report = {
        "before": baseline,
        "after": rules_first,
        "delta_accuracy": rules_first["accuracy"] - baseline["accuracy"],
        "method": "manual prompt A/B (DSPy compile optional via build_dspy_module)",
        "sample_size": len(sample),
    }
    print(json.dumps(report, indent=2))

    out_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "docs", "sprint3", "dspy_prompt_ab_results.json"
    )
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Wrote {out_path}")

    try:
        build_dspy_module()
        print("dspy is installed — QueryWriterModule scaffold OK (compile loop not auto-run).")
    except ImportError as e:
        print(f"Note: {e}")


if __name__ == "__main__":
    main()
