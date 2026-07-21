"""
Sprint 1 spike — de-risking the riskiest assumption in the system.

Riskiest assumption (risk register #1, #6, #7): "our deterministic Verifier checks
can actually catch a wrong-but-plausible query before it reaches the user."

Honest scope: this does not test a live Query Writer LLM (needs your API key, not
wired in yet). It tests whether the Verifier's rule-based logic distinguishes a
naive/wrong query from a correct one on the two real adversarial cases found in
Stage 2 profiling.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verifier"))
from checks import verify

CASES = [
    {
        "name": "Case 1: order count with multi-item orders (risk #6)",
        "question": "How many orders were placed?",
        "naive_sql": """
            SELECT COUNT(order_id) as order_count
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
        """,
        "naive_expectation": "FAIL — overcounts because 9.9% of orders have >1 item",
        "correct_sql": """
            SELECT COUNT(DISTINCT o.order_id) as order_count
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
        """,
        "correct_expectation": "PASS",
    },
    {
        "name": "Case 2: unique customer count (risk #7)",
        "question": "How many unique customers do we have?",
        "naive_sql": """
            SELECT COUNT(DISTINCT customer_id) as unique_customers
            FROM customers
        """,
        "naive_expectation": "FAIL — customer_id is issued per-order, not per-customer",
        "correct_sql": """
            SELECT COUNT(DISTINCT customer_unique_id) as unique_customers
            FROM customers
        """,
        "correct_expectation": "PASS",
    },
    {
        "name": "Case 3: hallucinated column (risk #4)",
        "question": "What's the average customer satisfaction rating?",
        "naive_sql": """
            SELECT AVG(customer_satisfaction_score) as avg_score
            FROM orders
        """,
        "naive_expectation": "FAIL — no such column exists; real column is review_score in order_reviews",
        "correct_sql": """
            SELECT AVG(review_score) as avg_score
            FROM order_reviews
        """,
        "correct_expectation": "PASS",
    },
]


def run_spike():
    print("=" * 78)
    print("SPRINT 1 SPIKE — testing whether Verifier catches known-wrong queries")
    print("=" * 78)

    results = []
    for case in CASES:
        print(f"\n{case['name']}")
        print(f"  Question: \"{case['question']}\"")

        naive_result = verify(case["naive_sql"])
        print(f"  Naive SQL  -> status={naive_result.status:6s} | expected: {case['naive_expectation']}")
        if naive_result.status == "fail":
            print(f"               reason: {naive_result.failure_reason}")
        naive_ok = (naive_result.status == "fail")

        correct_result = verify(case["correct_sql"])
        print(f"  Correct SQL -> status={correct_result.status:6s} (row_count={correct_result.row_count}) | expected: {case['correct_expectation']}")
        correct_ok = (correct_result.status == "pass")

        case_passed = naive_ok and correct_ok
        results.append(case_passed)
        print(f"  >> SPIKE RESULT: {'CONFIRMED' if case_passed else 'FAILED'}")

    print("\n" + "=" * 78)
    n_passed = sum(results)
    print(f"SPIKE SUMMARY: {n_passed}/{len(results)} cases confirmed")
    print("=" * 78)
    return n_passed == len(results)


if __name__ == "__main__":
    success = run_spike()
    sys.exit(0 if success else 1)
