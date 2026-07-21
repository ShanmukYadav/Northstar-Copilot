"""
Narrator agent - turns a verified result into a plain-language answer.

v3 (pipeline wiring): now returns token usage for real cost tracking.

MODEL TIER NOTE: architecture.md section 5 specs Claude Sonnet 5 as default; this file
calls Haiku 4.5 as a deliberate temporary simplification, matching evaluation_plan.md
section 6's planned Haiku-vs-Sonnet A/B - treat this as that A/B's cheap-path arm.
To switch to Sonnet: confirm the exact current OpenRouter slug at openrouter.ai/models
before hardcoding it.

CRITICAL per the sandbox-leak design (agent_contract_result_verifier.md): this agent
receives ONLY the verified result set and the already-sanitized SQL.

Design source: docs/stage3_design/agent_contracts.json (narrator_output contract).
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


def narrate(question: str, sql: str, result_rows: list, assumptions: list = None) -> dict:
    context = f"""Question: {question}
SQL (already verified): {sql}
Result rows: {result_rows}
Assumptions made by the query: {assumptions or []}
"""
    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",  # TEMPORARY - see module docstring
        messages=[
            {"role": "system", "content": NARRATOR_SYSTEM_PROMPT},
            {"role": "user", "content": context},
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
        return {"answer_text": None, "confidence_label": "low_escalated",
                "parse_error": f"{e}, raw={raw[:200]}", "_usage": usage}

    result["sql_shown"] = sql
    result["_usage"] = usage
    return result


if __name__ == "__main__":
    test_result = narrate(
        question="How many unique customers do we have?",
        sql="SELECT COUNT(DISTINCT customer_unique_id) AS unique_customers FROM customers",
        result_rows=[(96096,)],
    )
    print(json.dumps(test_result, indent=2))
