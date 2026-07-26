"""
End-to-end pipeline — Sprint 3/4.

Topology (orchestration_decision_record.md):
  Router
    → out_of_scope: refuse
    → ambiguous: Clarifier (ask / assume / escalate)
    → comparative: Planner → Query Writer × N → Verifier → Narrator
    → standard_query: Query Writer → Verifier (retry-once) → Narrator

Sprint 3+ upgrades:
- Clarifier + Planner live
- All LLM calls via gateway (cost, retries, fallbacks, LLM cache)
- Exact-match question cache for repeated successful answers
- API kwargs: user_reply, use_question_cache, narrator_strong
"""
from __future__ import annotations

import os
import sys
import time
from typing import Optional

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "verifier"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sandbox"))

from router import classify
from clarifier import clarify
from planner import plan
from query_writer import write_query
from narrator import narrate
from checks import verify
from build_db import get_readonly_connection
from gateway.cache import question_cache, make_key
from gateway.client import get_cost_summary


def _step_cost(agent_out: dict) -> float:
    if not agent_out:
        return 0.0
    if agent_out.get("_cost_usd") is not None:
        return float(agent_out["_cost_usd"])
    usage = agent_out.get("_usage")
    if not usage:
        return 0.0
    return (usage.get("prompt_tokens", 0) * 1e-6
            + usage.get("completion_tokens", 0) * 5e-6)


# Concepts that do not exist in our Olist v1 schema (PRD: ground or refuse).
_SCHEMA_GAPS = {
    "email": "email / e-mail address",
    "e-mail": "email / e-mail address",
    "phone": "phone number",
    "mobile": "phone number",
    "telephone": "phone number",
    "age": "customer age",
    "birthday": "date of birth",
    "date of birth": "date of birth",
    "gender": "gender",
    "full name": "customer full name",
    "customer name": "customer full name",
    "password": "password / login credentials",
    "login": "login / session data",
    "gps": "GPS / geolocation coordinates",
    "latitude": "geolocation",
    "longitude": "geolocation",
    "distance between": "seller-customer distance (geolocation not in this dataset)",
    "instagram": "marketing / ad platform data",
    "facebook ads": "marketing / ad platform data",
}


def _detect_schema_gaps(question: str) -> list[str]:
    q = (question or "").lower()
    found = []
    for key, label in _SCHEMA_GAPS.items():
        if key in q and label not in found:
            found.append(label)
    return found


def _cannot_answer_message(qw_result: dict | None, question: str = "") -> str:
    """User-facing explanation when the schema cannot support the question."""
    reason = None
    missing = []
    if qw_result:
        reason = qw_result.get("cannot_answer_reason") or qw_result.get("parse_error")
        missing = list(qw_result.get("missing_fields") or [])

    # Always merge deterministic detections from the question text
    for gap in _detect_schema_gaps(question):
        if gap not in missing and gap not in str(missing):
            missing.append(gap)

    # Prefer a concrete, human sentence for known gaps
    if any("email" in str(m).lower() for m in missing) or "email" in (question or "").lower():
        reason = (
            reason
            or "This dataset has no customer email field, so I cannot count duplicates by email"
        )

    q_hint = ""
    if missing:
        miss = ", ".join(str(m) for m in missing)
        q_hint = f" Missing from this database: {miss}."

    base = (
        reason
        or "This question needs data that is not in the Olist tables available to me"
    )
    schema_help = (
        " Available customer fields: customer_id, customer_unique_id, "
        "customer_zip_code_prefix, customer_city, customer_state "
        "(no email, phone, or personal name). "
        "Try asking about unique customers (customer_unique_id), orders, "
        "payments, reviews, product categories, or sellers."
    )
    return f"{base.rstrip('.')}." f"{q_hint}{schema_help}"


def _run_query_writer_with_retry(question: str, trace: dict) -> tuple[Optional[dict], Optional[object], bool]:
    """Returns (qw_result, v_result, retried). qw_result kept even on cannot_answer."""
    qw_result = write_query(question)
    trace["steps"].append({"agent": "query_writer", "output": qw_result})
    trace["total_cost"] += _step_cost(qw_result)

    if qw_result.get("cannot_answer") or not qw_result.get("sql"):
        return qw_result, None, False

    v_result = verify(qw_result["sql"])
    trace["steps"].append({"agent": "verifier", "output": v_result.to_dict()})

    retried = False
    if v_result.status != "pass":
        retried = True
        qw_result = write_query(question, retry_feedback=v_result.failure_reason)
        trace["steps"].append({"agent": "query_writer_retry", "output": qw_result})
        trace["total_cost"] += _step_cost(qw_result)

        if qw_result.get("cannot_answer") or not qw_result.get("sql"):
            return qw_result, None, retried

        v_result = verify(qw_result["sql"])
        trace["steps"].append({"agent": "verifier_retry", "output": v_result.to_dict()})

    if v_result.status != "pass":
        return qw_result, v_result, retried

    return qw_result, v_result, retried


def _fetch_rows(sql: str) -> list:
    con = get_readonly_connection()
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def answer_question(
    question: str,
    *,
    user_reply: str | None = None,
    use_question_cache: bool = True,
    narrator_strong: bool = False,
) -> dict:
    """
    Answer a business question end-to-end.

    user_reply: optional follow-up when the prior turn was needs_clarification.
    use_question_cache: exact-match cache for successful answers.
    narrator_strong: use stronger narrator model tier (A/B).
    """
    cache_key = make_key("question", question, extra=user_reply or "")
    if use_question_cache and user_reply is None:
        cached = question_cache.get(cache_key)
        if cached is not None:
            out = dict(cached)
            out["from_cache"] = True
            return out

    trace: dict = {
        "question": question,
        "steps": [],
        "total_cost": 0.0,
        "from_cache": False,
    }
    t0 = time.time()

    # 1. Router
    route = classify(question)
    trace["steps"].append({"agent": "router", "output": route})
    trace["total_cost"] += _step_cost(route)
    category = route.get("category")

    if category == "out_of_scope":
        trace["final_answer"] = (
            "This request is outside what I can help with (read-only analytics only)."
        )
        trace["status"] = "refused"
        trace["latency_seconds"] = time.time() - t0
        return trace

    # 2. Ambiguous → Clarifier
    if category == "ambiguous":
        clar = clarify(
            question,
            ambiguity_reason=route.get("reason", ""),
            user_reply=user_reply,
        )
        trace["steps"].append({"agent": "clarifier", "output": clar})
        trace["total_cost"] += _step_cost(clar)

        if clar.get("mode") == "ask_user":
            trace["final_answer"] = clar.get("clarifying_question") or (
                "Could you clarify what metric, time range, and filters you mean?"
            )
            trace["status"] = "needs_clarification"
            trace["clarifying_question"] = trace["final_answer"]
            trace["latency_seconds"] = time.time() - t0
            return trace

        if clar.get("mode") == "escalate":
            trace["final_answer"] = (
                "This question still needs a human analyst "
                f"({clar.get('escalation_reason') or 'unclear after clarification'})."
            )
            trace["status"] = "escalate"
            trace["latency_seconds"] = time.time() - t0
            return trace

        # state_assumption → continue with resolved question
        resolved = clar.get("resolved_question") or question
        trace["stated_assumption"] = clar.get("stated_assumption")
        question_for_sql = resolved
        category = "standard_query"
    else:
        question_for_sql = question

    # 3. Comparative → Planner multi-step
    if category == "comparative":
        plan_out = plan(question_for_sql)
        trace["steps"].append({"agent": "planner", "output": plan_out})
        trace["total_cost"] += _step_cost(plan_out)
        steps = plan_out.get("steps") or [
            {"step_id": 1, "query_intent": question_for_sql, "depends_on": None}
        ]

        all_sql = []
        all_rows = []
        all_assumptions = []
        retried_any = False

        for step in steps:
            intent = step.get("query_intent") or question_for_sql
            qw_result, v_result, retried = _run_query_writer_with_retry(intent, trace)
            retried_any = retried_any or retried
            if qw_result is not None and (qw_result.get("cannot_answer") or not qw_result.get("sql")):
                trace["final_answer"] = _cannot_answer_message(qw_result, question_for_sql)
                trace["status"] = "cannot_answer"
                trace["retried"] = retried_any
                trace["latency_seconds"] = time.time() - t0
                return trace
            if qw_result is None or v_result is None or v_result.status != "pass":
                trace["final_answer"] = (
                    "I couldn't verify a correct answer for one step of this comparison "
                    "- escalating to the team."
                )
                trace["status"] = "escalate"
                trace["retried"] = retried_any
                trace["latency_seconds"] = time.time() - t0
                return trace
            rows = _fetch_rows(qw_result["sql"])
            all_sql.append(qw_result["sql"])
            all_rows.extend(rows)
            all_assumptions.extend(qw_result.get("assumptions_stated") or [])

        combined_sql = "\n-- step separator --\n".join(all_sql)
        nar_result = narrate(
            question=question_for_sql,
            sql=combined_sql,
            result_rows=all_rows[:50],
            assumptions=all_assumptions,
            strong=narrator_strong,
        )
        trace["steps"].append({"agent": "narrator", "output": nar_result})
        trace["total_cost"] += _step_cost(nar_result)
        trace["final_answer"] = nar_result.get("answer_text")
        trace["sql_shown"] = combined_sql
        trace["confidence"] = nar_result.get("confidence_label")
        trace["status"] = "answered"
        trace["retried"] = retried_any
        trace["plan_steps"] = len(steps)
        trace["latency_seconds"] = time.time() - t0
        if use_question_cache and user_reply is None and trace["status"] == "answered":
            question_cache.set(cache_key, {k: v for k, v in trace.items() if k != "steps"})
        return trace

    # 4. Standard path (single query)
    qw_result, v_result, retried = _run_query_writer_with_retry(question_for_sql, trace)

    if qw_result is not None and (qw_result.get("cannot_answer") or not qw_result.get("sql")):
        if retried:
            trace["final_answer"] = (
                "I couldn't produce a verified query for this question after a retry. "
                + _cannot_answer_message(qw_result, question_for_sql)
            )
            trace["status"] = "escalate"
        else:
            trace["final_answer"] = _cannot_answer_message(qw_result, question_for_sql)
            trace["status"] = "cannot_answer"
        trace["retried"] = retried
        trace["latency_seconds"] = time.time() - t0
        return trace

    if qw_result is None:
        trace["final_answer"] = "I couldn't produce a verified query for this question."
        trace["status"] = "escalate"
        trace["retried"] = retried
        trace["latency_seconds"] = time.time() - t0
        return trace

    if v_result is None or v_result.status != "pass":
        trace["final_answer"] = (
            "I couldn't verify a correct answer to this question - escalating to the team."
        )
        trace["status"] = "escalate"
        trace["retried"] = retried
        trace["latency_seconds"] = time.time() - t0
        return trace

    result_rows = _fetch_rows(qw_result["sql"])
    nar_result = narrate(
        question=question_for_sql,
        sql=qw_result["sql"],
        result_rows=result_rows,
        assumptions=qw_result.get("assumptions_stated"),
        strong=narrator_strong,
    )
    trace["steps"].append({"agent": "narrator", "output": nar_result})
    trace["total_cost"] += _step_cost(nar_result)

    trace["final_answer"] = nar_result.get("answer_text")
    trace["sql_shown"] = qw_result["sql"]
    trace["confidence"] = nar_result.get("confidence_label")
    trace["status"] = "answered"
    trace["retried"] = retried
    trace["latency_seconds"] = time.time() - t0

    if use_question_cache and user_reply is None and trace["status"] == "answered":
        question_cache.set(cache_key, dict(trace))

    return trace


def answer_questions_concurrent(
    questions: list[str],
    *,
    max_workers: int = 20,
) -> list[dict]:
    """Burst helper for concurrent-load measurement."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    results: list[Optional[dict]] = [None] * len(questions)
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(answer_question, q): i for i, q in enumerate(questions)
        }
        for fut in as_completed(futures):
            i = futures[fut]
            try:
                results[i] = fut.result()
            except Exception as e:
                results[i] = {
                    "question": questions[i],
                    "status": "error",
                    "final_answer": str(e),
                    "total_cost": 0.0,
                    "latency_seconds": 0.0,
                }
    return results  # type: ignore[return-value]


if __name__ == "__main__":
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
    print(f"From cache: {result.get('from_cache', False)}")
    print(f"Latency: {result['latency_seconds']:.2f}s")
    print(f"Cost: ${result['total_cost']:.5f}")
