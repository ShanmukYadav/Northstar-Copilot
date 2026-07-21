"""
Router / Classifier agent - first live LLM call in the pipeline.

v3 (pipeline wiring): now returns token usage for real cost tracking.

Design source: docs/stage3_design/architecture.md section 2 (topology) and
docs/stage3_design/agent_contracts.json (router_output schema).

Category set collapsed from 6 to 4 in Sprint 2 after empirical evaluation - see
docs/stage3_design/orchestration_decision_record.md addendum.

Job: classify question SHAPE only. It does NOT judge whether a question is a "trap"
(e.g. the join-grain or customer_id adversarial cases) - that's the Verifier's job
downstream.
"""
import os
import json
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

CATEGORIES = ["standard_query", "comparative", "ambiguous", "out_of_scope"]

ROUTER_SYSTEM_PROMPT = """You are a classifier for a business-analytics copilot over an e-commerce dataset (orders, products, customers, sellers, reviews, payments).
Classify the user's question into exactly one category:
- standard_query: answerable by a single query against the data - a direct count, filter, GROUP BY aggregation, ranking, or a time-series/date-bucketed breakdown - as long as it needs only ONE query and has one clear interpretation
- comparative: compares two or more distinct entities (e.g. two states, two categories) and needs more than one query or a multi-step plan
- ambiguous: the question has no single correct interpretation without more information (e.g. "why are sales down", undefined terms like "performance")
- out_of_scope: asks to modify/update/delete data, or is unrelated to the dataset

Respond with ONLY a JSON object, no other text: {"category": "...", "confidence": 0.0-1.0, "reason": "one sentence"}
"""


def classify(question: str) -> dict:
    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[
            {"role": "system", "content": ROUTER_SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()

    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
    } if response.usage else None

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as e:
        return {"category": "out_of_scope", "confidence": 0.0,
                "reason": f"PARSE_ERROR: {e}, raw={raw[:200]}", "_usage": usage}

    if result.get("category") not in CATEGORIES:
        return {"category": "out_of_scope", "confidence": 0.0,
                "reason": f"INVALID_CATEGORY: {result.get('category')}", "_usage": usage}

    result["_usage"] = usage
    return result


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "How many orders were delivered?"
    print(json.dumps(classify(q), indent=2))
