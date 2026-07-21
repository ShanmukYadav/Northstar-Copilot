"""
Evaluation harness v1.

Sprint 1 scope: no live Query Writer agent yet (needs your API key). This harness:
  1. Executes every gold_sql in the golden set against the REAL sandbox and confirms
     it runs cleanly and produces a sane result.
  2. Runs every gold_sql through the real Verifier checks, to confirm the golden set's
     own "correct" queries don't trip false-positive failures.
  3. Reports category composition.

Sprint 2 extends this to real system-vs-gold execution accuracy once the Query Writer
agent exists.
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src", "verifier"))
from checks import verify

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "golden_set", "golden_set_v1.json")


def load_golden_set():
    with open(GOLDEN_SET_PATH) as f:
        return json.load(f)


def run_harness():
    golden_set = load_golden_set()
    print("=" * 78)
    print(f"EVALUATION HARNESS v1 — {len(golden_set)} questions in golden set")
    print("=" * 78)

    category_counts = {}
    executable_pass = 0
    executable_total = 0
    verifier_false_positives = []

    for item in golden_set:
        cat = item["category"]
        category_counts[cat] = category_counts.get(cat, 0) + 1

        if item.get("gold_sql") is None:
            print(f"  {item['id']:8s} [{cat:24s}] no gold_sql (expected behavior: {item.get('expected_behavior')}) — skipped")
            continue

        executable_total += 1
        result = verify(item["gold_sql"])
        if result.status == "pass":
            executable_pass += 1
            print(f"  {item['id']:8s} [{cat:24s}] gold_sql executes and passes Verifier (row_count={result.row_count})")
        else:
            verifier_false_positives.append((item["id"], result.failure_reason))
            print(f"  {item['id']:8s} [{cat:24s}] *** VERIFIER REJECTED A GOLD QUERY: {result.failure_reason}")

    print("\n" + "-" * 78)
    print("CATEGORY COMPOSITION (golden set v1, n={})".format(len(golden_set)))
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"  {cat:24s} {count:>3d}  ({100*count/len(golden_set):.0f}%)")

    print("\n" + "-" * 78)
    print(f"GOLD-SQL SELF-VALIDATION: {executable_pass}/{executable_total} gold queries execute cleanly and pass the Verifier")
    if verifier_false_positives:
        print(f"*** {len(verifier_false_positives)} FALSE POSITIVE(S):")
        for qid, reason in verifier_false_positives:
            print(f"    - {qid}: {reason}")
    else:
        print("No false positives — the Verifier does not block any known-correct query.")
    print("=" * 78)

    return len(verifier_false_positives) == 0


if __name__ == "__main__":
    success = run_harness()
    sys.exit(0 if success else 1)
