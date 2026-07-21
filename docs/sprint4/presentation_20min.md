# 20-minute presentation script

**Format:** Recorded talk for Demo Day (brief: Product ~6 · Architecture ~7 · Engineering ~7).  
**Live demo:** run API UI in the Product segment (or Engineering if preferred).

**Before recording**
1. `uvicorn src.api.app:app --port 8000` and confirm `/ready`  
2. Have three questions ready (happy / clarify / refuse)  
3. Optional: open `docs/sprint3/eval_pipeline_results.json` for metrics slide  

---

## Segment 1 — Product (~6 min)

### Slide / beat 1 — The problem (45s)
> Northstar promises: type a business question, get a trustworthy answer. Reality: analysts are a bottleneck, and a wrong query returns a **confident wrong number**. We’re not building a demo text-to-SQL toy—we’re building an auditable analytics copilot.

### Beat 2 — Users (45s)
> **Priya** needs answers without SQL. **Devon** should only see escalations. **Sam** wants comparisons with the query visible. **Jordan** cares about cost and audit. That maps to metrics: accuracy, faithfulness, ambiguity floor, latency, cost.

### Beat 3 — Scope (30s)
> v1 on **Olist**: multi-table e-commerce, real join-grain and customer-id traps. In scope: ask, clarify, refuse, verify, explain. Out: writes, geo, marketing funnel.

### Beat 4 — Metrics we hit (60s)
> Golden set **18/18 (100%)** with semantic result matching. Cost about **0.3 cents** per question. Sequential p95 about **8.4 seconds**. Ambiguous questions clarify; destructive refuse. Latency under 20 concurrent is residual—we measured 10 workers.

### Beat 5 — Live demo (~2.5 min)
1. Open http://localhost:8000/  
2. **Happy path:** “How many unique customers do we have?” → answer + SQL (`customer_unique_id`)  
3. **Comparative:** SP vs RJ delivery time (or top category) → show SQL exposed  
4. **Ambiguous:** “Why are sales down?” → clarification, no number  
5. **Refuse:** “Update the price of product X to $50.” → refused  

**Line to say:** “The query is always shown—trust is structural, not vibes.”

---

## Segment 2 — Solution architecture (~7 min)

### Beat 1 — Topology (90s)
> Hybrid control flow: **Router** first. Simple path is sequential: Query Writer → Verifier → Narrator. **Comparative** adds Planner. **Ambiguous** goes to Clarifier. Out-of-scope stops at the router. Specialists are single-responsibility so we can swap models without rewriting the graph.

### Beat 2 — What we rejected (45s)
> We rejected planning every question—it taxes the 80% simple volume. We rejected multi-agent debate on the hot path—our bugs are join grain and wrong keys; deterministic checks beat two LLMs arguing.

### Beat 3 — Gateway & routing (90s)
> Every model call goes through one **gateway**: task-type routing, retries, fallbacks, cost log. Agents don’t hold provider keys. Cheap tier for router/clarifier; mid for SQL; narrator default cheap after A/B.

### Beat 4 — Verifier as risk control (90s)
> Highest risk: wrong query, confident answer. Verifier is a **hard gate**: read-only, schema allowlist, join-grain DISTINCT, customer_unique_id, execute on sandbox. Retry once with failure reason, then escalate—never invent.

### Beat 5 — Contracts & registry (45s)
> JSON contracts between agents; versioned **agent registry**. Swappable, viva-explainable.

*Point at architecture diagram in `docs/stage3_design/architecture.md` if sharing screen.*

---

## Segment 3 — Engineering (~7 min)

### Beat 1 — Build path (60s)
> Sprint 0–1 product/design/risk. Sprint 2 core path. Sprint 3 full agents, gateway, cache, concurrency harness, 18/18. Sprint 4 API, UI, runbook, SLOs, baseline benchmark.

### Beat 2 — Data & sandbox (45s)
> Olist in DuckDB read-only. Synthetic set for coverage; golden 18 locked for regression. We profiled real traps before writing agents.

### Beat 3 — Eval & baseline (90s)
> Execution accuracy compares **result sets**, not SQL strings—so ROUND and extra columns don’t false-fail if the metric is right. Baseline single Query Writer also hits 15/15 on gold_sql—**honest**: value of the stack is safety behavior and product path, not a magic accuracy gap on easy items. Pipeline costs more hops (~$0.003 vs ~$0.002).

### Beat 4 — Scale & cost (60s)
> Exact-match caches; concurrent runner. Burst 10/10 answered. Token economics under $0.02 ceiling. Cheap narrator won A/B.

### Beat 5 — Operate (60s)
> FastAPI + UI. `/health`, `/ready`, `/metrics`. Runbook, SLOs, canary/rollback for prompt changes. One-command deploy for pilot: uvicorn.

### Beat 6 — Limitations (45s)
> Thin golden set; no RAGAS number yet; no 20-worker formal test; no Chroma retrieval. We know where it fails next—and we don’t hide it.

**Close (15s):**  
> Correct. Auditable. Cost-aware. Ready to demo and defend.

---

## Timing card

| Segment | Minutes | Owner (if split) |
|---------|---------|------------------|
| Product + demo | 0:00–6:00 | Product lens |
| Architecture | 6:00–13:00 | Architecture lens |
| Engineering | 13:00–20:00 | Engineering lens |

## Recording tips

- Show UI at 1080p; zoom SQL panel  
- Cut long waits: pre-warm with one question or enable cache for second take  
- State residuals out loud—examiners reward honesty  
