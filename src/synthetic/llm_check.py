"""
LLM-check validation leg - closes the gap flagged in generate_v1.py's own honesty note.

Runs AFTER rules-based validation (checks.py::verify). Judges question/SQL fluency and
question-SQL alignment, which a deterministic rule cannot judge. This is leg 2 of the
brief's required 3-leg validation (rules, LLM check, human spot-check) - leg 3 (human
spot-check) still needs the team, not code, and is not addressed here.

Cost note: ~100 items, short prompts, Haiku tier - expect well under $0.05 total for a
full run. Cheap enough to run freely, but batch it once rather than on every dev loop.
"""
import os
import json
import sys
from dotenv import load_dotenv
load_dotenv()
from openai import OpenAI

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set"))

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

SYNTHETIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "synthetic_v1.json")

LLM_CHECK_PROMPT = """You are reviewing a synthetic (question, SQL) pair generated for testing a text-to-SQL system over an e-commerce dataset.

Question: {question}
SQL: {sql}

Judge two things:
1. natural: does the question read like something a real business user would actually ask (not awkward or robotic)?
2. aligned: does the SQL actually answer what the question asks (ignore whether it's the only possible correct SQL - just check it answers the question)?

Respond with ONLY a JSON object: {{"natural": true/false, "aligned": true/false, "issue": "one sentence if either is false, else null"}}
"""


def llm_check_item(question: str, sql: str) -> dict:
    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[{"role": "user", "content": LLM_CHECK_PROMPT.format(question=question, sql=sql)}],
        temperature=0,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        return {"natural": None, "aligned": None, "issue": f"PARSE_ERROR: {e}, raw={raw[:150]}"}


def run_llm_check():
    with open(SYNTHETIC_PATH) as f:
        items = json.load(f)

    print("=" * 78)
    print(f"LLM-CHECK VALIDATION LEG - {len(items)} synthetic items")
    print("=" * 78)

    flagged = []
    for item in items:
        sql = item.get("gold_sql")
        if sql is None:
            continue
        result = llm_check_item(item["question"], sql)
        item["llm_check"] = result
        if result.get("natural") is False or result.get("aligned") is False:
            flagged.append((item["id"], result))
            print(f"  {item['id']:30s} FLAGGED: {result.get('issue')}")

    with open(SYNTHETIC_PATH, "w") as f:
        json.dump(items, f, indent=2)

    print("\n" + "-" * 78)
    print(f"{len(flagged)}/{len(items)} items flagged by LLM check")
    if flagged:
        print("Review these manually before including them in the locked golden set (Stage 5/6).")
    else:
        print("No issues flagged - all synthetic items read naturally and align with their SQL.")
    print(f"Updated file written to {SYNTHETIC_PATH} (each item now has an 'llm_check' field)")
    print("=" * 78)


if __name__ == "__main__":
    run_llm_check()
