"""
Full pipeline evaluation - the system-level counterpart to eval_router.py and
eval_query_writer.py (which tested agents individually). This runs the whole thing
(Router -> Query Writer -> Verifier -> retry-once -> Narrator) against every golden-set
question and checks the right BEHAVIOR happened, not just whether SQL matched:
  - standard_query/comparative/etc items with gold_sql: expect status "answered" AND
    the SQL executed matches gold (reusing the date-normalized comparison fix)
  - ambiguous items: expect status "needs_clarification" (never a guessed answer)
  - out_of_scope items: expect status "refused"

This is Sprint 2's "first evaluation and cost baseline" exit criterion, measured for
real, at the system level.
"""
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sandbox"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verifier"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from pipeline import answer_question
from build_db import get_readonly_connection

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "golden_set_v1.json")


def normalize_row(row):
    return tuple(v.date() if isinstance(v, datetime.datetime) else v for v in row)


def get_gold_result(sql):
    con = get_readonly_connection()
    try:
        rows = con.execute(sql).fetchall()
        return sorted(normalize_row(r) for r in rows)
    except Exception:
        return None
    finally:
        con.close()


def get_pipeline_sql_result(sql):
    if not sql:
        return None
    con = get_readonly_connection()
    try:
        rows = con.execute(sql).fetchall()
        return sorted(normalize_row(r) for r in rows)
    except Exception:
        return None
    finally:
        con.close()


def run_eval():
    with open(GOLDEN_SET_PATH) as f:
        golden_set = json.load(f)

    print("=" * 78)
    print(f"FULL PIPELINE EVALUATION - {len(golden_set)} golden-set questions")
    print("Router -> Query Writer -> Verifier -> retry-once -> Narrator")
    print("=" * 78)

    total = len(golden_set)
    correct_behavior = 0
    total_cost = 0.0
    latencies = []

    for item in golden_set:
        result = answer_question(item["question"])
        total_cost += result["total_cost"]
        latencies.append(result["latency_seconds"])

        expected_behavior = item.get("expected_behavior")
        is_correct = False
        detail = ""

        if expected_behavior == "clarify":
            is_correct = (result["status"] == "needs_clarification")
            detail = f"status={result['status']}"
        elif expected_behavior == "refuse":
            is_correct = (result["status"] == "refused")
            detail = f"status={result['status']}"
        elif item.get("gold_sql"):
            if result["status"] == "answered":
                gold_rows = get_gold_result(item["gold_sql"])
                qw_rows = get_pipeline_sql_result(result.get("sql_shown"))
                is_correct = (gold_rows == qw_rows)
                detail = "SQL result matches gold" if is_correct else f"MISMATCH: gold={gold_rows} got={qw_rows}"
            else:
                detail = f"expected answered, got status={result['status']}"
        else:
            detail = "no expectation defined for this item - skipped from scoring"
            total -= 1
            continue

        if is_correct:
            correct_behavior += 1
        status_label = "PASS" if is_correct else "FAIL"
        print(f"  {item['id']:8s} [{status_label}] {result['status']:20s} "
              f"cost=${result['total_cost']:.5f} latency={result['latency_seconds']:.1f}s")
        if not is_correct:
            print(f"           {detail}")

    latencies.sort()
    p50 = latencies[len(latencies)//2] if latencies else 0
    p95 = latencies[int(len(latencies)*0.95)] if latencies else 0

    print("\n" + "-" * 78)
    print(f"SYSTEM-LEVEL PIPELINE ACCURACY: {correct_behavior}/{total} ({100*correct_behavior/total:.0f}%)")
    print(f"Total cost for full run: ${total_cost:.5f}")
    print(f"Average cost per question: ${total_cost/len(golden_set):.5f}")
    print(f"Latency - p50: {p50:.2f}s, p95: {p95:.2f}s (single-request, no concurrency yet)")
    print("=" * 78)
    print("\nNote: latency here is sequential/single-request. PRD section 6's latency")
    print("guardrail (p95 <= 8s/15s) is specified UNDER 20 concurrent requests - this")
    print("run does not test that condition. Concurrent load testing is Stage 6/7 work.")


if __name__ == "__main__":
    run_eval()
