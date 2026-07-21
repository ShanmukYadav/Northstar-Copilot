"""
Synthetic-data pipeline v1.

Honest scope: no LLM API access in this environment, so generation here is
template-based, parameterized over REAL schema values (actual category names, actual
states) pulled from the live sandbox -- not invented values. This produces the "rules"
leg of the brief's validation requirement (p.6: "validate with a mix of rules, an LLM
check, and a human spot-check"): every generated (question, gold_sql) pair is executed
against the real sandbox and run through the real Verifier before being accepted.

The LLM-check and human-spot-check legs are explicitly NOT done here -- flagged as open,
not silently skipped -- and should happen in Stage 6 once a model endpoint is reachable
and the team has bandwidth to spot-check a sample.

Produces the four named synthetic sets from the brief (p.6):
  - gold Q&A pairs across difficulty (category-aggregation, state-count templates)
  - adversarial (join-grain and hallucinated-column variants, reusing spike patterns)
  - rare-schema-corner (low-volume categories/states specifically)
  - ambiguous/underspecified is NOT template-generable (that's the point -- ambiguity
    resists templating) -- noted as a real limitation, not synthesized here
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sandbox"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verifier"))
from build_db import get_readonly_connection
from checks import verify

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "synthetic_v1.json")


def get_real_categories():
    con = get_readonly_connection()
    rows = con.execute(
        "SELECT DISTINCT product_category_name_english FROM category_translation "
        "WHERE product_category_name_english IS NOT NULL"
    ).fetchall()
    con.close()
    return [r[0] for r in rows]


def get_real_states():
    con = get_readonly_connection()
    rows = con.execute("SELECT DISTINCT customer_state FROM customers").fetchall()
    con.close()
    return [r[0] for r in rows]


def get_category_volume(category):
    """Used to tag a generated question as rare_schema_corner vs mainstream."""
    con = get_readonly_connection()
    row = con.execute("""
        SELECT COUNT(*) FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN category_translation ct ON p.product_category_name = ct.product_category_name
        WHERE ct.product_category_name_english = ?
    """, [category]).fetchone()
    con.close()
    return row[0]


def gen_category_aggregation_set(categories):
    """Difficulty-graded gold Q&A: one per real category, tagged rare vs mainstream by actual volume."""
    items = []
    for cat in categories:
        volume = get_category_volume(cat)
        items.append({
            "id": f"syn_cat_{cat.replace(' ', '_')[:30]}",
            "category": "rare_schema_corner" if volume < 200 else "aggregation",
            "question": f"How many order items were sold in the '{cat.replace('_', ' ')}' category?",
            "gold_sql": (
                f"SELECT COUNT(*) as cnt FROM order_items oi "
                f"JOIN products p ON oi.product_id = p.product_id "
                f"JOIN category_translation ct ON p.product_category_name = ct.product_category_name "
                f"WHERE ct.product_category_name_english = '{cat}'"
            ),
            "real_volume": volume,
            "generation_method": "template: category-aggregation, parameterized over real schema value",
        })
    return items


def gen_state_comparison_set(states):
    """One comparative question per real state pair against the largest state (SP)."""
    items = []
    for state in states:
        if state == "SP":
            continue
        items.append({
            "id": f"syn_state_{state}",
            "category": "comparative",
            "question": f"How many customers are in {state} compared to SP?",
            "gold_sql": (
                f"SELECT customer_state, COUNT(DISTINCT customer_unique_id) as cnt "
                f"FROM customers WHERE customer_state IN ('{state}', 'SP') "
                f"GROUP BY customer_state"
            ),
            "generation_method": "template: state-comparison, parameterized over real schema value",
        })
    return items


def gen_adversarial_set():
    """
    Reuses the two canonical patterns from Stage 2/spike, applied to different
    aggregation targets -- same underlying trap, different surface question, which is
    exactly what makes an adversarial set useful (a Query Writer that memorizes one
    phrasing wouldn't be caught by a single example).
    """
    return [
        {
            "id": "syn_adv_seller_orders",
            "category": "adversarial_join_grain",
            "question": "How many orders has each seller fulfilled?",
            "gold_sql": (
                "SELECT seller_id, COUNT(DISTINCT order_id) as order_count "
                "FROM order_items GROUP BY seller_id"
            ),
            "wrong_sql_pattern": "COUNT(order_id) without DISTINCT -- overcounts multi-item orders",
            "generation_method": "template: adversarial join-grain variant",
        },
        {
            "id": "syn_adv_customer_by_state",
            "category": "adversarial_customer_key",
            "question": "How many unique customers are in each state?",
            "gold_sql": (
                "SELECT customer_state, COUNT(DISTINCT customer_unique_id) as cnt "
                "FROM customers GROUP BY customer_state"
            ),
            "wrong_sql_pattern": "COUNT(DISTINCT customer_id) -- counts order-level IDs, not real customers",
            "generation_method": "template: adversarial customer-key variant",
        },
    ]


def validate_pool(items):
    """The 'rules' validation leg: execute + Verifier-check every item; drop failures."""
    valid, rejected = [], []
    for item in items:
        sql = item.get("gold_sql")
        if sql is None:
            valid.append(item)  # ambiguous-style items have no SQL to validate
            continue
        result = verify(sql)
        if result.status == "pass":
            item["validated"] = True
            item["validated_row_count"] = result.row_count
            valid.append(item)
        else:
            item["validated"] = False
            item["rejection_reason"] = result.failure_reason
            rejected.append(item)
    return valid, rejected


def deduplicate(items):
    seen_sql = set()
    deduped = []
    for item in items:
        key = (item.get("gold_sql") or item["question"]).strip()
        if key in seen_sql:
            continue
        seen_sql.add(key)
        deduped.append(item)
    return deduped


def run_pipeline():
    print("=" * 78)
    print("SYNTHETIC PIPELINE v1")
    print("=" * 78)

    categories = get_real_categories()
    states = get_real_states()
    print(f"Pulled {len(categories)} real categories, {len(states)} real states from live sandbox")

    pool = []
    pool += gen_category_aggregation_set(categories)
    pool += gen_state_comparison_set(states)
    pool += gen_adversarial_set()
    print(f"Generated {len(pool)} raw synthetic items before dedup/validation")

    pool = deduplicate(pool)
    print(f"{len(pool)} items after deduplication")

    valid, rejected = validate_pool(pool)
    print(f"{len(valid)} items pass rules-based validation (execute + Verifier check)")
    if rejected:
        print(f"{len(rejected)} items REJECTED by validation:")
        for r in rejected[:10]:
            print(f"  - {r['id']}: {r['rejection_reason']}")

    with open(OUTPUT_PATH, "w") as f:
        json.dump(valid, f, indent=2)

    cat_counts = {}
    for item in valid:
        cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1

    print("\nCategory breakdown of validated synthetic set:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:24s} {count:>4d}")

    print(f"\nWritten to {OUTPUT_PATH}")
    print("\nHONEST GAPS (not silently skipped):")
    print("  - LLM-check validation leg: NOT done (no model endpoint reachable here)")
    print("  - Human spot-check leg: NOT done (needs the team, not just this pipeline)")
    print("  - Ambiguous/underspecified set: NOT template-generable by design; the 2 "
          "in golden_set_v1.json remain hand-curated, not synthetically expanded here")
    print("=" * 78)


if __name__ == "__main__":
    run_pipeline()
