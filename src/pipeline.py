"""
End-to-end pipeline: Router -> Query Writer -> Verifier -> retry-once -> Narrator.

This is the "core agent path working end-to-end" from Sprint 2's exit criteria
(brief cadence table). First time all four pieces run together as one system rather
than being tested independently.

Known simplifications, stated honestly rather than hidden:
- Ambiguous questions: the Clarifier agent isn't built yet. This pipeline detects
  "ambiguous" and stops with a clarification-needed response instead of guessing -
  which is the correct SAFETY behavior even without the Clarifier's actual back-and-forth
  UX built. Never guesses; just doesn't yet ask a *good* clarifying question.
- Comparative questions: the Planner's multi-step decomposition isn't built yet.
  Routed to the same single Query Writer call as standard_query - this worked fine in
  Sprint 2 testing (gs010/gs011 both answered correctly with one query using IN/GROUP
  BY) but will NOT scale to a question that genuinely needs multiple separate queries
  merged together. Flagged as a real gap, not silently papered over.
- No real LLM gateway (architecture.md section 4) - calls go direct per-agent. Same gap
  noted in STATUS.md; not re-solved here.
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "verifier"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sandbox"))
from router import classify
from query_writer import write_query
from narrator import narrate
from checks import verify
from build_db import get_readonly_connection

# Haiku 4.5 pricing (per OpenRouter, confirm current rate at openrouter.ai/models
# before trusting this for a large batch run - see architecture.md section 5)
HAIKU_INPUT_PER_TOKEN = 1.00 / 1_000_000
HAIKU_OUTPUT_PER_TOKEN = 5.00 / 1_000_000


def _cost(usage):
    if not usage:
        return 0.0
    return (usage["prompt_tokens"] * HAIKU_INPUT_PER_TOKEN
            + usage["completion_tokens"] * HAIKU_OUTPUT_PER_TOKEN)


def answer_question(question: str) -> dict:
    trace = {"question": question, "steps": [], "total_cost": 0.0}
    t0 = time.time()

    # 1. Router
    route = classify(question)
    trace["steps"].append({"agent": "router", "output": route})
    trace["total_cost"] += _cost(route.get("_usage"))

    if route["category"] == "out_of_scope":
        trace["final_answer"] = "This request is outside what I can help with (read-only analytics only)."
        trace["status"] = "refused"
        trace["latency_seconds"] = time.time() - t0
        return trace

    if route["category"] == "ambiguous":
        trace["final_answer"] = (
            f"This question needs clarification before I can answer it accurately "
            f"(reason: {route.get('reason')}). Rather than guess, I'm flagging this "
            f"for a follow-up question."
        )
        trace["status"] = "needs_clarification"
        trace["latency_seconds"] = time.time() - t0
        return trace

    # 2. Query Writer (with retry-once on Verifier failure, per architecture.md)
    qw_result = write_query(question)
    trace["steps"].append({"agent": "query_writer", "output": qw_result})
    trace["total_cost"] += _cost(qw_result.get("_usage"))

    if qw_result.get("cannot_answer") or not qw_result.get("sql"):
        trace["final_answer"] = "I don't have the data needed to answer this question."
        trace["status"] = "cannot_answer"
        trace["latency_seconds"] = time.time() - t0
        return trace

    v_result = verify(qw_result["sql"])
    trace["steps"].append({"agent": "verifier", "output": v_result.to_dict()})

    retried = False
    if v_result.status != "pass":
        retried = True
        qw_result = write_query(question, retry_feedback=v_result.failure_reason)
        trace["steps"].append({"agent": "query_writer_retry", "output": qw_result})
        trace["total_cost"] += _cost(qw_result.get("_usage"))

        if qw_result.get("cannot_answer") or not qw_result.get("sql"):
            trace["final_answer"] = "I couldn't produce a verified query for this question."
            trace["status"] = "escalate"
            trace["latency_seconds"] = time.time() - t0
            return trace

        v_result = verify(qw_result["sql"])
        trace["steps"].append({"agent": "verifier_retry", "output": v_result.to_dict()})

    if v_result.status != "pass":
        trace["final_answer"] = "I couldn't verify a correct answer to this question - escalating to the team."
        trace["status"] = "escalate"
        trace["retried"] = retried
        trace["latency_seconds"] = time.time() - t0
        return trace

    # 3. Get the actual result rows to narrate
    con = get_readonly_connection()
    try:
        result_rows = con.execute(qw_result["sql"]).fetchall()
    finally:
        con.close()

    # 4. Narrator
    nar_result = narrate(
        question=question,
        sql=qw_result["sql"],
        result_rows=result_rows,
        assumptions=qw_result.get("assumptions_stated"),
    )
    trace["steps"].append({"agent": "narrator", "output": nar_result})
    trace["total_cost"] += _cost(nar_result.get("_usage"))

    trace["final_answer"] = nar_result.get("answer_text")
    trace["sql_shown"] = qw_result["sql"]
    trace["confidence"] = nar_result.get("confidence_label")
    trace["status"] = "answered"
    trace["retried"] = retried
    trace["latency_seconds"] = time.time() - t0
    return trace


if __name__ == "__main__":
    import sys
    import json
    q = sys.argv[1] if len(sys.argv) > 1 else "How many unique customers do we have?"
    result = answer_question(q)
    print(f"\nQuestion: {result['question']}")
    print(f"Status: {result['status']}")
    print(f"Answer: {result.get('final_answer')}")
    if result.get("sql_shown"):
        print(f"SQL shown: {result['sql_shown']}")
    print(f"Confidence: {result.get('confidence')}")
    print(f"Retried: {result.get('retried', False)}")
    print(f"Latency: {result['latency_seconds']:.2f}s")
    print(f"Cost: ${result['total_cost']:.5f}")
