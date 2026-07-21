"""
Query Writer agent - produces SQL grounded in the real Olist schema.

v3 (pipeline wiring): added retry_feedback param, implementing the retry-once rule
from architecture.md ("if the Verifier fails, retry the Query Writer step exactly once
with the failure reason as added context") - this existed as a diagram edge before now,
not as code. Also now returns token usage for real cost tracking (PRD section 6/7
cost guardrail currently only has a projected number).

Design source: docs/stage3_design/agent_contracts.json (query_writer_output contract).
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

SCHEMA_CONTEXT = """
TABLES (DuckDB, read-only):
- orders(order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date)
- order_items(order_id, order_item_id, product_id, seller_id, price, freight_value, shipping_limit_date)
- order_payments(order_id, payment_type, payment_installments, payment_value)
- order_reviews(review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp)
- products(product_id, product_category_name)
- customers(customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state)
- sellers(seller_id, seller_zip_code_prefix, seller_city, seller_state)
- category_translation(product_category_name, product_category_name_english)

CRITICAL RULES (violating these produces a wrong answer, verified against real data):
1. JOIN GRAIN: orders to order_items is ONE-TO-MANY - 9.9% of real orders have more
   than one line item. If your query joins order_items and counts orders, you MUST use
   COUNT(DISTINCT order_id), never COUNT(order_id) or COUNT(*).
2. CUSTOMER IDENTITY: customers.customer_id is issued PER ORDER, not per real customer
   (99,441 customer_id vs only 96,096 customer_unique_id in the real data). Any question
   about "unique customers" or "how many customers" MUST use
   COUNT(DISTINCT customer_unique_id), never customer_id.
3. Only reference tables/columns listed above. Never invent a column name. If the
   question needs something not in this schema (e.g. geolocation, marketing data),
   set "cannot_answer" to true instead of guessing a column name.
4. SQL must be read-only SELECT. Never write INSERT/UPDATE/DELETE/DROP.
5. State every non-obvious assumption you make (e.g. "filtered to order_status =
   'delivered'") in assumptions_stated - do not silently assume.
6. DATE ARITHMETIC: to compute the difference between two timestamp/date columns
   (e.g. delivery time), use DATE_DIFF('day', start_col, end_col). Do NOT subtract
   two timestamps and CAST the result to INTEGER - DuckDB does not support casting an
   INTERVAL to INTEGER and this will fail at execution. DATE_DIFF is the only
   supported approach for date-difference calculations in this environment.
"""

QUERY_WRITER_SYSTEM_PROMPT = f"""You are a SQL query writer for a business-analytics copilot over a real e-commerce dataset.

{SCHEMA_CONTEXT}

Given a business question, write ONE DuckDB SQL SELECT query that answers it correctly.

Respond with ONLY a JSON object, no other text:
{{
  "sql": "the SELECT query",
  "tables_used": ["table1", "table2"],
  "columns_used": ["col1", "col2"],
  "assumptions_stated": ["assumption 1", "assumption 2"],
  "cannot_answer": false
}}

If the question cannot be answered from the schema above, set cannot_answer to true and
sql to null - do not invent columns or tables to force an answer.
"""


def write_query(question: str, retry_feedback: str = None) -> dict:
    user_content = question
    if retry_feedback:
        user_content = (
            f"{question}\n\n"
            f"Your previous attempt failed verification with this reason: "
            f"{retry_feedback}\n"
            f"Write a corrected query that fixes this specific issue."
        )

    response = client.chat.completions.create(
        model="anthropic/claude-haiku-4.5",
        messages=[
            {"role": "system", "content": QUERY_WRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
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
        return {"sql": None, "tables_used": [], "columns_used": [],
                "assumptions_stated": [], "cannot_answer": True,
                "parse_error": f"{e}, raw={raw[:200]}", "_usage": usage}

    result["_usage"] = usage
    return result


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "How many unique customers do we have?"
    print(json.dumps(write_query(q), indent=2))
