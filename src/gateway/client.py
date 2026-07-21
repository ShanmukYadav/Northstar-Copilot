"""
LLM Gateway — single point every model call passes through.

Implements architecture.md §4 responsibilities without requiring agents to know
provider keys, model slugs, or retry policy:

- Task-type routing (agents request a *task*, not a model name)
- Timeout + retry with exponential backoff
- Fallback chain when primary model fails
- Cost accounting per call and process summary
- Optional LLM response cache (exact-match)

Provider path: OpenRouter via OpenAI-compatible API (same as Sprint 2 agents).
Interface is LiteLLM-shaped so a future swap is a one-file change.
"""
from __future__ import annotations

import os
import time
import threading
from typing import Any, Optional

from dotenv import load_dotenv

load_dotenv()

from .cache import llm_cache, make_key

# Production routing policy (architecture.md §5) — OpenRouter slugs.
# Dev can override via env NORTHSTAR_MODEL_<TASK> e.g. NORTHSTAR_MODEL_ROUTER=...
TASK_ROUTING: dict[str, dict[str, Any]] = {
    "router": {
        "model": "anthropic/claude-haiku-4.5",
        "fallback": ["google/gemini-2.5-flash-lite", "anthropic/claude-haiku-4.5"],
        "temperature": 0,
    },
    "clarifier": {
        "model": "anthropic/claude-haiku-4.5",
        "fallback": ["google/gemini-2.5-flash-lite"],
        "temperature": 0,
    },
    "planner": {
        "model": "anthropic/claude-haiku-4.5",
        "fallback": ["anthropic/claude-sonnet-4"],
        "temperature": 0,
    },
    "query_writer": {
        "model": "anthropic/claude-haiku-4.5",
        "fallback": ["anthropic/claude-sonnet-4"],
        "temperature": 0,
    },
    "narrator": {
        # Temporary cheap-path default (Sprint 2 A/B arm); use narrator_strong for Sonnet
        "model": "anthropic/claude-haiku-4.5",
        "fallback": ["anthropic/claude-haiku-4.5"],
        "temperature": 0,
    },
    "narrator_strong": {
        "model": "anthropic/claude-sonnet-4",
        "fallback": ["anthropic/claude-haiku-4.5"],
        "temperature": 0,
    },
}

# $/token estimates (OpenRouter list prices; reconfirm before large batch billing claims)
PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-haiku-4.5": (1.00 / 1_000_000, 5.00 / 1_000_000),
    "anthropic/claude-sonnet-4": (3.00 / 1_000_000, 15.00 / 1_000_000),
    "google/gemini-2.5-flash-lite": (0.10 / 1_000_000, 0.40 / 1_000_000),
}

_DEFAULT_PRICING = (1.00 / 1_000_000, 5.00 / 1_000_000)

_lock = threading.Lock()
_cost_log: list[dict] = []
_client = None


def _get_client():
    global _client
    if _client is None:
        from openai import OpenAI

        api_key = os.environ.get("OPENROUTER_API_KEY")
        if not api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY is not set. Put it in .env (never commit secrets)."
            )
        _client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
    return _client


def _resolve_model(task: str) -> dict[str, Any]:
    if task not in TASK_ROUTING:
        raise ValueError(f"Unknown gateway task '{task}'. Known: {list(TASK_ROUTING)}")
    cfg = dict(TASK_ROUTING[task])
    env_key = f"NORTHSTAR_MODEL_{task.upper()}"
    if os.environ.get(env_key):
        cfg["model"] = os.environ[env_key]
    return cfg


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    inp, out = PRICING.get(model, _DEFAULT_PRICING)
    return prompt_tokens * inp + completion_tokens * out


def get_cost_summary() -> dict:
    with _lock:
        total = sum(c["cost_usd"] for c in _cost_log)
        return {
            "calls": len(_cost_log),
            "total_cost_usd": total,
            "by_task": _group_by(_cost_log, "task"),
            "entries": list(_cost_log),
        }


def reset_cost_summary() -> None:
    with _lock:
        _cost_log.clear()


def _group_by(entries: list[dict], key: str) -> dict:
    out: dict[str, dict] = {}
    for e in entries:
        k = e.get(key, "unknown")
        bucket = out.setdefault(k, {"calls": 0, "cost_usd": 0.0})
        bucket["calls"] += 1
        bucket["cost_usd"] += e["cost_usd"]
    return out


def complete(
    task: str,
    messages: list[dict],
    *,
    use_cache: bool = True,
    max_retries: int = 2,
    timeout_s: float = 30.0,
) -> dict:
    """
    Make a chat completion for a named task.

    Returns:
      {
        "content": str,
        "model": str,
        "usage": {"prompt_tokens": int, "completion_tokens": int},
        "cost_usd": float,
        "cached": bool,
        "fallback_used": bool,
      }
    """
    cfg = _resolve_model(task)
    primary = cfg["model"]
    chain = [primary] + [m for m in cfg.get("fallback", []) if m != primary]
    temperature = cfg.get("temperature", 0)

    cache_key = None
    if use_cache:
        cache_key = make_key(task, json_dumps(messages))
        hit = llm_cache.get(cache_key)
        if hit is not None:
            out = dict(hit)
            out["cached"] = True
            return out

    last_err: Optional[Exception] = None
    for attempt, model in enumerate(chain):
        for retry in range(max_retries + 1):
            try:
                client = _get_client()
                t0 = time.time()
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    timeout=timeout_s,
                )
                latency = time.time() - t0
                content = (response.choices[0].message.content or "").strip()
                usage = {
                    "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                    "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                }
                cost = _estimate_cost(model, usage["prompt_tokens"], usage["completion_tokens"])
                result = {
                    "content": content,
                    "model": model,
                    "usage": usage,
                    "cost_usd": cost,
                    "cached": False,
                    "fallback_used": model != primary,
                    "latency_seconds": latency,
                    "task": task,
                }
                with _lock:
                    _cost_log.append(
                        {
                            "task": task,
                            "model": model,
                            "cost_usd": cost,
                            "prompt_tokens": usage["prompt_tokens"],
                            "completion_tokens": usage["completion_tokens"],
                            "fallback_used": result["fallback_used"],
                        }
                    )
                if use_cache and cache_key:
                    # Don't store cost_log side effects; store response payload only
                    llm_cache.set(cache_key, {
                        "content": content,
                        "model": model,
                        "usage": usage,
                        "cost_usd": 0.0,  # cached responses do not re-bill
                        "cached": True,
                        "fallback_used": result["fallback_used"],
                        "latency_seconds": 0.0,
                        "task": task,
                    })
                return result
            except Exception as e:
                last_err = e
                if retry < max_retries:
                    time.sleep(0.5 * (2 ** retry))
                continue
        # try next model in fallback chain
        continue

    raise RuntimeError(
        f"Gateway exhausted fallbacks for task='{task}' models={chain}: {last_err}"
    )


def json_dumps(obj: Any) -> str:
    import json
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)
