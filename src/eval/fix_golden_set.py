"""
Fix golden_set_v1.json based on a real finding from live Query Writer testing:

1. gs007's original gold_sql joined order_items unnecessarily, silently excluding 775
   real orders (603 unavailable + 164 canceled, verified against the sandbox) that
   were genuinely placed but never got a line-item record. "How many orders were
   placed" should count ALL orders in the orders table - fixed to match.

2. Because gs007 no longer needs a join, it stopped testing the join-grain adversarial
   case it was designed for. Added gs018 as a genuine replacement: a question that
   MUST join order_items (needs price data) and where naive COUNT vs
   COUNT(DISTINCT) genuinely differ (22,455 vs 21,026, verified against the sandbox) -
   unlike the old gs007, this one can't be sidestepped by skipping the join.
"""
import json
import os

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "golden_set_v1.json")


def fix():
    with open(GOLDEN_SET_PATH) as f:
        golden_set = json.load(f)

    for item in golden_set:
        if item["id"] == "gs007":
            item["gold_sql"] = "SELECT COUNT(DISTINCT order_id) as cnt FROM orders"
            item["notes"] = (
                "FIXED after live Query Writer testing revealed a bug in the original "
                "gold_sql: it joined order_items unnecessarily, silently excluding 775 "
                "real orders (603 unavailable + 164 canceled, verified against the "
                "sandbox) that were placed but never got a line-item row. 'Orders "
                "placed' means all orders in the orders table, full stop - no join "
                "needed. See gs018 for the actual join-grain adversarial test, which "
                "this question no longer covers."
            )

    golden_set.append({
        "id": "gs018",
        "category": "adversarial_join_grain",
        "question": "How many orders included at least one item priced over R$150?",
        "gold_sql": "SELECT COUNT(DISTINCT order_id) as cnt FROM order_items WHERE price > 150",
        "notes": (
            "Replacement for gs007 as the real join-grain adversarial test. This "
            "question genuinely requires touching order_items.price, so it cannot be "
            "sidestepped by skipping the join (unlike the old gs007). Verified: naive "
            "COUNT(order_id) gives 22,455, correct COUNT(DISTINCT order_id) gives "
            "21,026 - a real 1,429-order overcounting gap if DISTINCT is omitted."
        ),
    })

    with open(GOLDEN_SET_PATH, "w") as f:
        json.dump(golden_set, f, indent=2)

    print(f"Fixed gs007's gold_sql (removed unnecessary join)")
    print(f"Added gs018 as the real join-grain adversarial test")
    print(f"Golden set now has {len(golden_set)} items")


if __name__ == "__main__":
    fix()
