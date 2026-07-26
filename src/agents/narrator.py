"""
Narrator agent - turns a verified result into a plain-language answer.

Sprint 3/4: gateway-routed. Default task=narrator (cheap path / Haiku).
Pass strong=True to use narrator_strong (Sonnet) for A/B comparisons.
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.client import complete

NARRATOR_SYSTEM_PROMPT = """You are a business analyst explaining a query result to a non-technical user.

You will be given: the original question, the SQL that was run (already verified correct), and the exact result rows.

Write a short, plain-language answer (2-4 sentences). Rules:
1. Every number in your answer MUST come directly from the result rows given to you. Never compute, estimate, or round in a way that changes the value.
2. Do not add caveats or interpretations not supported by the data (e.g. don't speculate on WHY a number is what it is unless the data shows it).
3. If the result has multiple rows (e.g. a trend or comparison), summarize the pattern briefly rather than listing every row.
4. State your confidence: "high" if the question was clear and the data directly answers it, "medium" if there's a reasonable assumption baked in (e.g. a status filter), "low_escalated" if you're not confident the result actually answers what was asked.

Respond with ONLY a JSON object, no other text:
{"answer_text": "...", "confidence_label": "high | medium | low_escalated"}
"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def narrate(
    question: str,
    sql: str,
    result_rows: list,
    assumptions: list | None = None,
    *,
    strong: bool = False,
) -> dict:
    context = f"""Question: {question}
SQL (already verified): {sql}
Result rows: {result_rows}
Assumptions made by the query: {assumptions or []}
"""
    task = "narrator_strong" if strong else "narrator"
    gw = complete(
        task,
        [
            {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
            {"role": "user", "content": context},
        ],
    )
    usage = gw.get("usage")
    try:
        result = _parse_json(gw["content"])
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "answer_text": None,
            "confidence_label": "low_escalated",
            "parse_error": f"{e}, raw={str(gw.get('content'))[:200]}",
            "_usage": usage,
            "_cost_usd": gw.get("cost_usd", 0.0),
            "_model": gw.get("model"),
        }

    result["sql_shown"] = sql
    result["_usage"] = usage
    result["_cost_usd"] = gw.get("cost_usd", 0.0)
    result["_model"] = gw.get("model")
    result["_cached"] = gw.get("cached", False)
    return result


if __name__ == "__main__":
    test_result = narrate(
        question="How many unique customers do we have?",
        sql="SELECT COUNT(DISTINCT customer_unique_id) AS unique_customers FROM customers",
        result_rows=[(96096,)],
    )
    print(json.dumps(test_result, indent=2))
