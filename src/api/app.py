"""
Sprint 4 — FastAPI service for Northstar Insight Copilot.

Endpoints:
  GET  /health     — liveness + dependency checks
  GET  /ready      — ready if sandbox DB is readable
  POST /ask        — answer a business question
  GET  /           — minimal demo UI
  GET  /metrics    — lightweight process metrics (cache + cost summary)

Run from repo root:
  uvicorn src.api.app:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

import os
import sys
import time
import traceback
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

# Repo layout: src/api/app.py → put src/ on path
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_ROOT = os.path.abspath(os.path.join(_SRC, ".."))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)
for sub in ("agents", "verifier", "sandbox", "gateway"):
    p = os.path.join(_SRC, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

load_dotenv(os.path.join(_ROOT, ".env"))

from pipeline import answer_question  # noqa: E402
from gateway.cache import question_cache, llm_cache  # noqa: E402
from gateway.client import get_cost_summary  # noqa: E402
from build_db import DB_PATH, get_readonly_connection  # noqa: E402

app = FastAPI(
    title="Northstar Insight Copilot",
    description="Autonomous analytics: NL question → verified SQL answer",
    version="4.0.0",
)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Process-level counters for ops
_REQUESTS = {"total": 0, "answered": 0, "errors": 0, "refused": 0, "clarify": 0, "escalate": 0}
_STARTED = time.time()


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_reply: Optional[str] = Field(
        None, description="Optional follow-up after needs_clarification"
    )
    use_cache: bool = True


class AskResponse(BaseModel):
    status: str
    answer: Optional[str] = None
    sql_shown: Optional[str] = None
    confidence: Optional[str] = None
    clarifying_question: Optional[str] = None
    stated_assumption: Optional[str] = None
    latency_seconds: float
    cost_usd: float
    from_cache: bool = False
    retried: bool = False


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - _STARTED, 1),
        "version": "4.0.0",
    }


@app.get("/ready")
def ready() -> dict[str, Any]:
    checks = {"sandbox_db": False, "openrouter_key": False}
    try:
        if os.path.exists(DB_PATH):
            con = get_readonly_connection()
            con.execute("SELECT 1").fetchone()
            con.close()
            checks["sandbox_db"] = True
    except Exception as e:
        checks["sandbox_error"] = str(e)
    checks["openrouter_key"] = bool(os.environ.get("OPENROUTER_API_KEY"))
    ok = checks["sandbox_db"] and checks["openrouter_key"]
    if not ok:
        raise HTTPException(status_code=503, detail=checks)
    return {"status": "ready", "checks": checks}


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    return {
        "requests": dict(_REQUESTS),
        "question_cache": question_cache.stats(),
        "llm_cache": llm_cache.stats(),
        "gateway_cost": get_cost_summary(),
        "uptime_seconds": round(time.time() - _STARTED, 1),
    }


@app.post("/ask", response_model=AskResponse)
def ask(body: AskRequest) -> AskResponse:
    _REQUESTS["total"] += 1
    q = body.question.strip()
    if not q:
        raise HTTPException(status_code=400, detail="question is empty")

    try:
        result = answer_question(
            q,
            user_reply=body.user_reply,
            use_question_cache=body.use_cache,
        )
    except Exception as e:
        _REQUESTS["errors"] += 1
        raise HTTPException(
            status_code=500,
            detail={"error": str(e), "trace": traceback.format_exc()[-800:]},
        ) from e

    status = result.get("status") or "error"
    if status == "answered":
        _REQUESTS["answered"] += 1
    elif status == "refused":
        _REQUESTS["refused"] += 1
    elif status == "needs_clarification":
        _REQUESTS["clarify"] += 1
    elif status == "escalate":
        _REQUESTS["escalate"] += 1

    return AskResponse(
        status=status,
        answer=result.get("final_answer"),
        sql_shown=result.get("sql_shown"),
        confidence=result.get("confidence"),
        clarifying_question=result.get("clarifying_question") or (
            result.get("final_answer") if status == "needs_clarification" else None
        ),
        stated_assumption=result.get("stated_assumption"),
        latency_seconds=float(result.get("latency_seconds") or 0),
        cost_usd=float(result.get("total_cost") or 0),
        from_cache=bool(result.get("from_cache")),
        retried=bool(result.get("retried")),
    )


@app.get("/", response_class=HTMLResponse)
def index():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)
    return HTMLResponse("<h1>Northstar Copilot API</h1><p>POST /ask</p>")
