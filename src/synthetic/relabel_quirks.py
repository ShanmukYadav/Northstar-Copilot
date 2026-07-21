"""
Relabel synthetic items where the LLM check flagged a REAL Olist data-quality quirk
(typo/duplication/naming oddity in the source category_translation table itself) rather
than a pipeline bug. Verified against the live sandbox before this script was written -
every one of these category names genuinely exists as-is in Olist's official
product_category_name_english column.

These are NOT dropped: a Query Writer that can't handle a real, messy category name is
exactly the kind of failure the brief warns about (p.5, schema grounding). Relabeling
makes their purpose explicit instead of leaving them mislabeled as plain "aggregation".
"""
import json
import os

SYNTHETIC_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "synthetic_v1.json")

# IDs confirmed against the real sandbox as genuine source-data quirks, not template bugs
REAL_DATA_QUIRK_IDS = {
    "syn_cat_tablets_printing_image",
    "syn_cat_market_place",
    "syn_cat_costruction_tools_tools",
    "syn_cat_la_cuisine",
    "syn_cat_construction_tools_constructio",
    "syn_cat_kitchen_dining_laundry_garden_",
    "syn_cat_costruction_tools_garden",
    "syn_cat_home_confort",
    "syn_cat_fashio_female_clothing",
}


def relabel():
    with open(SYNTHETIC_PATH) as f:
        items = json.load(f)

    relabeled = 0
    for item in items:
        if item["id"] in REAL_DATA_QUIRK_IDS:
            item["category"] = "adversarial_messy_schema_value"
            item["notes"] = (
                "LLM-check flagged this question as awkward-reading; verified against "
                "the real sandbox - the category name IS genuinely stored this way in "
                "Olist's category_translation table (typo/duplication in the source "
                "data itself, not a pipeline bug). Kept as a robustness test: the "
                "Query Writer must use the real stored value even when it reads oddly."
            )
            relabeled += 1

    with open(SYNTHETIC_PATH, "w") as f:
        json.dump(items, f, indent=2)

    print(f"Relabeled {relabeled} items to 'adversarial_messy_schema_value'")
    print(f"Written back to {SYNTHETIC_PATH}")

    cat_counts = {}
    for item in items:
        cat_counts[item["category"]] = cat_counts.get(item["category"], 0) + 1
    print("\nUpdated category breakdown:")
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:32s} {count:>4d}")


if __name__ == "__main__":
    relabel()
