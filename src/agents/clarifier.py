"""
Clarifier agent — Sprint 3 (full agent set).

Intercepts ambiguous questions and either:
  - ask_user: returns a specific clarifying question (preferred)
  - state_assumption: states one interpretation when the user already replied
  - escalate: hands off to human queue after one failed clarification round

Contract: docs/stage3_design/agent_contracts.json → clarifier_output
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.client import complete

CLARIFIER_SYSTEM = """You are the Clarifier for a business-analytics copilot over e-commerce data
(orders, products, customers, sellers, reviews, payments).

The Router already labeled this question as AMBIGUOUS. Your job is to NOT guess.
Either ask one crisp clarifying question, or (if the user already answered a prior
clarification) restate a single explicit assumption and produce a resolved question.

Respond with ONLY a JSON object:
{
  "mode": "ask_user" | "state_assumption" | "escalate",
  "clarifying_question": "string or null",
  "stated_assumption": "string or null",
  "escalation_reason": "string or null",
  "resolved_question": "string or null"
}

Rules:
1. Prefer mode=ask_user with ONE specific clarifying_question.
2. If user_reply is provided and is enough, use mode=state_assumption, set
   stated_assumption and resolved_question (a fully specified version of the original).
3. If still unclear after a user reply, use mode=escalate.
4. Never invent numbers or SQL.
"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def clarify(
    question: str,
    ambiguity_reason: str = "",
    user_reply: str | None = None,
) -> dict:
    user_content = (
        f"Original question: {question}\n"
        f"Router ambiguity reason: {ambiguity_reason or 'unspecified'}\n"
        f"User reply to prior clarification: {user_reply if user_reply is not None else '(none yet)'}\n"
    )
    gw = complete(
        "clarifier",
        [
            {"role": "system", "content": CLARIFIER_SYSTEM},
            {"role": "user", "content": user_content},
        ],
    )
    usage = gw.get("usage")
    try:
        result = _parse_json(gw["content"])
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "mode": "escalate",
            "clarifying_question": None,
            "stated_assumption": None,
            "escalation_reason": f"PARSE_ERROR: {e}",
            "resolved_question": None,
            "_usage": usage,
            "_cost_usd": gw.get("cost_usd", 0.0),
            "_model": gw.get("model"),
        }

    mode = result.get("mode")
    if mode not in ("ask_user", "state_assumption", "escalate"):
        result["mode"] = "ask_user"
        if not result.get("clarifying_question"):
            result["clarifying_question"] = (
                "Could you specify the metric, time range, and filter (e.g. order status) you mean?"
            )

    result["_usage"] = usage
    result["_cost_usd"] = gw.get("cost_usd", 0.0)
    result["_model"] = gw.get("model")
    result["_cached"] = gw.get("cached", False)
    return result


if __name__ == "__main__":
    import sys as _sys
    q = _sys.argv[1] if len(_sys.argv) > 1 else "Why are sales down?"
    print(json.dumps(clarify(q, ambiguity_reason="no single metric"), indent=2))
