# Viva prep (15–20 min individual)

Examiner can open any file. Goal: explain decisions you did **not** personally write.

## 60-second system pitch

> We turn a plain-language question into a verified answer over Olist. Router classifies; Clarifier never guesses; Planner only on comparative; Query Writer emits SQL; **deterministic Verifier** hard-gates; Narrator explains with SQL exposed. Gateway owns models, cost, retries, cache. FastAPI + UI for operate.

## Likely questions & strong answers

### Why this orchestration, not pure plan-and-execute?
Simple lookups are most of the volume. Planning every request burns latency and cost for no accuracy gain. Comparative is the exception path.

### Why not multi-agent debate?
Failure modes are structural (join grain, wrong customer key, hallucinated columns). Rules catch them cheaper and more reliably than two LLMs arguing.

### How does verification work?
Read-only keyword check, schema allowlist, join-grain DISTINCT, customer_unique_id rule, execute on DuckDB, row-count sanity. Fail → retry Query Writer once with reason → else escalate.

### What does a successful question cost?
About **$0.003** on the cheap path (Sprint 3–4). Ceiling **$0.02**. Baseline QW-only ~$0.002. Narrator A/B: keep Haiku default.

### Latency?
Sequential golden p95 ~**8.4s**. Burst 10 workers p95 ~**9.8s**. PRD wants 20 concurrent—residual, not hidden.

### Why 100% baseline and 100% pipeline?
Golden set is small and aligned with our prompts. Honest: stack’s win is **clarify/refuse/retry/narrate**, not a huge SQL accuracy delta yet. Next: harder golden set + RAGAS.

### gs010 / gs004 stories?
- **gs010:** agent rounded and added COUNT; metrics correct; eval was too brittle → semantic match.  
- **gs004:** Portuguese vs English category; same category id; map PT↔EN + prefer English in QW.

### Where would it fail?
Hard multi-hop not covered by gold; rephrased questions miss exact cache; model outage if fallbacks exhausted; wrong business definition not in schema (semantic layer thin).

### Kill switch?
Verifier double-fail → escalate, don’t guess. Gateway fallbacks exhausted → error. Operator can stop uvicorn.

### How do you change a model safely?
Canary 3 questions (happy/clarify/refuse) + pytest; optional full eval; rollback git + restart (`ops/canary_rollback.md`).

### Secrets?
Only `OPENROUTER_API_KEY` in `.env`; never in code.

## Files to navigate cold

| Topic | Path |
|-------|------|
| Pipeline | `src/pipeline.py` |
| Gateway | `src/gateway/client.py` |
| Verifier | `src/verifier/checks.py` |
| Match logic | `src/eval/result_match.py` |
| API | `src/api/app.py` |
| Architecture | `docs/stage3_design/architecture.md` |
| Risks | `docs/stage4_risk/risk_register.md` |
| Metrics | `docs/sprint3/sprint3_closeout.md` |

## Practice drill

1. Draw topology from memory (2 min).  
2. Trace “unique customers” through code (5 min).  
3. Explain one risk + mitigation without notes (2 min).  
4. State three residuals honestly (1 min).  
