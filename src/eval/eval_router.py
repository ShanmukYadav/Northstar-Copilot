"""
Router evaluation v2 - against the collapsed 4-category taxonomy (standard_query,
comparative, ambiguous, out_of_scope). See docs/stage3_design/orchestration_decision_record.md
addendum for why simple_lookup/aggregation/trend collapsed into standard_query.

Golden-set labels stay at the finer grain (simple_lookup, aggregation, trend,
rare_schema_corner, adversarial_hallucination) since they track test-coverage breadth,
not routing behavior - this map is what translates those finer labels into what the
Router is now actually expected to output.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
from router import classify

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "golden_set_v1.json")

EXPECTED_ROUTER_CATEGORY = {
    "simple_lookup": "standard_query",
    "aggregation": "standard_query",
    "trend": "standard_query",
    "rare_schema_corner": "standard_query",
    "adversarial_hallucination": "standard_query",
    "comparative": "comparative",
    "ambiguous": "ambiguous",
    "out_of_scope": "out_of_scope",
}


def run_eval():
    with open(GOLDEN_SET_PATH) as f:
        golden_set = json.load(f)

    print("=" * 78)
    print(f"ROUTER EVALUATION v2 - {len(golden_set)} golden-set questions")
    print("Taxonomy: standard_query / comparative / ambiguous / out_of_scope")
    print("=" * 78)

    correct = 0
    total = 0
    for item in golden_set:
        expected = EXPECTED_ROUTER_CATEGORY.get(item["category"])
        if expected is None:
            continue
        total += 1
        result = classify(item["question"])
        actual = result.get("category")
        match = (actual == expected)
        correct += match
        status = "PASS" if match else "FAIL"
        print(f"  {item['id']:8s} [{status}] expected={expected:14s} got={actual:14s} "
              f"conf={result.get('confidence')} - \"{item['question'][:50]}\"")
        if not match:
            print(f"           reason given: {result.get('reason')}")

    print("\n" + "-" * 78)
    print(f"ROUTER ACCURACY (v2 taxonomy): {correct}/{total} ({100*correct/total:.0f}%)")
    print("=" * 78)
    return correct, total


if __name__ == "__main__":
    run_eval()
