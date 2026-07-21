"""
Planner agent — Sprint 3 (full agent set).

Used on the comparative path: decomposes a multi-entity question into 1-4
ordered query intents. Query Writer still produces SQL per step.

Contract: docs/stage3_design/agent_contracts.json → planner_output
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.client import complete

PLANNER_SYSTEM = """You are the Planner for a business-analytics copilot over Olist e-commerce data.

Available tables (DuckDB): orders, order_items, order_payments, order_reviews,
products, customers, sellers, category_translation.

Given a comparative or multi-hop business question, produce an ordered plan of
1-4 SQL-shaped steps. Prefer the MINIMUM number of steps. Many comparisons can
be one query with GROUP BY / CASE / IN — use a single step when that works.

Respond with ONLY a JSON object:
{
  "steps": [
    {"step_id": 1, "query_intent": "plain-language description of what this query must return", "depends_on": null}
  ],
  "merge_strategy": "how to combine step results for the final answer, or null if one step"
}

Rules:
1. Max 4 steps. Prefer 1 when possible.
2. SP vs RJ (or any small fixed entity list) comparisons of ONE metric MUST be a
   single step whose intent says to return entity + metric via GROUP BY — not one
   step per entity.
3. Each query_intent must be answerable with one SELECT against the schema.
4. Do not write SQL yourself — only intents for the Query Writer.
5. depends_on is the prior step_id or null.
6. In the intent text, tell the Query Writer: only the columns needed, no ROUND
   unless asked, no extra COUNT columns.
"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def plan(question: str) -> dict:
    gw = complete(
        "planner",
        [
            {"role": "system", "content": PLANNER_SYSTEM},
            {"role": "user", "content": question},
        ],
    )
    usage = gw.get("usage")
    try:
        result = _parse_json(gw["content"])
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "steps": [
                {
                    "step_id": 1,
                    "query_intent": question,
                    "depends_on": None,
                }
            ],
            "merge_strategy": None,
            "parse_error": str(e),
            "_usage": usage,
            "_cost_usd": gw.get("cost_usd", 0.0),
            "_model": gw.get("model"),
        }

    steps = result.get("steps") or []
    if not steps:
        steps = [{"step_id": 1, "query_intent": question, "depends_on": None}]
    # Cap at 4 per contract
    steps = steps[:4]
    for i, s in enumerate(steps, start=1):
        s.setdefault("step_id", i)
        s.setdefault("depends_on", None)
        if "query_intent" not in s:
            s["query_intent"] = question

    result["steps"] = steps
    result.setdefault("merge_strategy", None if len(steps) == 1 else "compare side by side")
    result["_usage"] = usage
    result["_cost_usd"] = gw.get("cost_usd", 0.0)
    result["_model"] = gw.get("model")
    result["_cached"] = gw.get("cached", False)
    return result


if __name__ == "__main__":
    import sys as _sys
    q = _sys.argv[1] if len(_sys.argv) > 1 else "Compare average review score for SP vs RJ sellers"
    print(json.dumps(plan(q), indent=2))
