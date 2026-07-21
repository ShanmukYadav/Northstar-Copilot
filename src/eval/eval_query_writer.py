"""
Query Writer end-to-end evaluation v2 - fixes a comparison bug found in v1: raw tuple
equality treated datetime.datetime and datetime.date as different values even when
they represent the identical calendar date (e.g. DATE_TRUNC(...) vs DATE_TRUNC(...)::DATE).
Rows are now normalized (datetime -> date) before comparison. This was a bug in THIS
eval script, not in the Query Writer or the Verifier - the third distinct bug class
found this sprint, this time in the harness measuring the system rather than the
system itself.

First real measurement of the PRD's north-star metric (execution accuracy), replacing
the projected baseline (~55-65%, BIRD-anchored) in docs/prd.md section 6.
"""
import json
import os
import sys
import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "verifier"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sandbox"))
from query_writer import write_query
from checks import verify
from build_db import get_readonly_connection

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "evals", "golden_set", "golden_set_v1.json")


def normalize_row(row):
    return tuple(v.date() if isinstance(v, datetime.datetime) else v for v in row)


def get_result(sql):
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
    print("QUERY WRITER END-TO-END EVALUATION v2 (date-normalized comparison)")
    print("=" * 78)

    total = 0
    verifier_pass = 0
    result_match = 0

    for item in golden_set:
        if item.get("gold_sql") is None:
            continue
        total += 1

        qw_result = write_query(item["question"])
        if qw_result.get("cannot_answer") or not qw_result.get("sql"):
            print(f"  {item['id']:8s} [NO SQL] Query Writer declined to answer")
            continue

        qw_sql = qw_result["sql"]
        v_result = verify(qw_sql)

        if v_result.status != "pass":
            print(f"  {item['id']:8s} [VERIFIER REJECTED] {v_result.failure_reason}")
            continue

        verifier_pass += 1

        gold_rows = get_result(item["gold_sql"])
        qw_rows = get_result(qw_sql)
        match = (gold_rows == qw_rows)
        if match:
            result_match += 1

        status = "MATCH" if match else "MISMATCH"
        print(f"  {item['id']:8s} [{status}]")
        if not match:
            print(f"           gold={gold_rows}")
            print(f"           qw  ={qw_rows}")
            print(f"           QW SQL: {qw_sql}")

    print("\n" + "-" * 78)
    print(f"Verifier pass rate: {verifier_pass}/{total} ({100*verifier_pass/total:.0f}%)")
    print(f"EXECUTION ACCURACY (result matches gold): {result_match}/{total} ({100*result_match/total:.0f}%)")
    print("=" * 78)
    return result_match, total


if __name__ == "__main__":
    run_eval()
