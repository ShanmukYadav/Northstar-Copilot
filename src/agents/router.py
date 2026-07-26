"""
Router / Classifier agent - first hop in the pipeline.

Sprint 3/4: all model calls go through the LLM gateway (architecture.md §4).
Category set: standard_query | comparative | ambiguous | out_of_scope
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.client import complete

CATEGORIES = ["standard_query", "comparative", "ambiguous", "out_of_scope"]

ROUTER_SYSTEM_PROMPT = """You are a classifier for a business-analytics copilot over an e-commerce dataset (orders, products, customers, sellers, reviews, payments).
Classify the user's question into exactly one category:
- standard_query: answerable by a single query against the data - a direct count, filter, GROUP BY aggregation, ranking, or a time-series/date-bucketed breakdown - as long as it needs only ONE query and has one clear interpretation
- comparative: compares two or more distinct entities (e.g. two states, two categories) and needs more than one query or a multi-step plan
- ambiguous: the question has no single correct interpretation without more information (e.g. "why are sales down", undefined terms like "performance")
- out_of_scope: asks to modify/update/delete data, or is unrelated to the dataset

Respond with ONLY a JSON object, no other text: {"category": "...", "confidence": 0.0-1.0, "reason": "one sentence"}
"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def classify(question: str) -> dict:
    gw = complete(
        "router",
        [
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    )
    usage = gw.get("usage")
    try:
        result = _parse_json(gw["content"])
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "category": "out_of_scope",
            "confidence": 0.0,
            "reason": f"PARSE_ERROR: {e}, raw={str(gw.get('content'))[:200]}",
            "_usage": usage,
            "_cost_usd": gw.get("cost_usd", 0.0),
            "_model": gw.get("model"),
        }

    if result.get("category") not in CATEGORIES:
        return {
            "category": "out_of_scope",
            "confidence": 0.0,
            "reason": f"INVALID_CATEGORY: {result.get('category')}",
            "_usage": usage,
            "_cost_usd": gw.get("cost_usd", 0.0),
            "_model": gw.get("model"),
        }

    result["_usage"] = usage
    result["_cost_usd"] = gw.get("cost_usd", 0.0)
    result["_model"] = gw.get("model")
    result["_cached"] = gw.get("cached", False)
    return result


if __name__ == "__main__":
    import sys as _sys
    q = _sys.argv[1] if len(_sys.argv) > 1 else "How many orders were delivered?"
    print(json.dumps(classify(q), indent=2))
