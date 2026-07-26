"""
Query Writer agent - produces SQL grounded in the real Olist schema.

Sprint 3/4: model calls via LLM gateway; supports retry_feedback (retry-once rule).
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from gateway.client import complete

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
7. SELECT LIST DISCIPLINE: return ONLY columns the question asks for. Do not add
   extra COUNT(*) / sample-size columns "for context" unless the question asks how
   many orders/rows.
8. NO SILENT ROUNDING: do not wrap aggregates in ROUND(...) unless the user asks for
   rounded/display values. Return full-precision AVG/SUM so results are auditable.
9. COMPARISONS: prefer ONE query with GROUP BY / FILTER / CASE when comparing a few
   entities (e.g. SP vs RJ).
10. PRODUCT CATEGORIES (user-facing): products.product_category_name is Portuguese
    (e.g. cama_mesa_banho). When the question asks for a product category name,
    JOIN category_translation and return product_category_name_english
    (e.g. bed_bath_table). Never return only the Portuguese key for a ranking/
    "which category" answer unless the user explicitly asks for Portuguese labels.
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
  "cannot_answer": false,
  "cannot_answer_reason": null,
  "missing_fields": []
}}

If the question cannot be answered from the schema above:
- set cannot_answer to true and sql to null
- do NOT invent columns or tables
- set cannot_answer_reason to one clear sentence naming what is missing
  (e.g. "Olist customers table has no email column")
- set missing_fields to a short list of missing concepts (e.g. ["email"])
"""


def _parse_json(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()
    return json.loads(text)


def write_query(question: str, retry_feedback: str | None = None) -> dict:
    user_content = question
    if retry_feedback:
        user_content = (
            f"{question}\n\n"
            f"Your previous attempt failed verification with this reason: "
            f"{retry_feedback}\n"
            f"Write a corrected query that fixes this specific issue."
        )

    use_cache = retry_feedback is None
    gw = complete(
        "query_writer",
        [
            {"role": "system", "content": QUERY_WRITER_SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        use_cache=use_cache,
    )
    usage = gw.get("usage")
    try:
        result = _parse_json(gw["content"])
    except (json.JSONDecodeError, KeyError) as e:
        return {
            "sql": None,
            "tables_used": [],
            "columns_used": [],
            "assumptions_stated": [],
            "cannot_answer": True,
            "parse_error": f"{e}, raw={str(gw.get('content'))[:200]}",
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
    q = _sys.argv[1] if len(_sys.argv) > 1 else "How many unique customers do we have?"
    print(json.dumps(write_query(q), indent=2))
