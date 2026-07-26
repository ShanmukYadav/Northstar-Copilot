# Final Project Submission

**Futurense AI Clinic · Capstone Project 05**  
**Client persona:** Northstar Analytics  

---

## 1. Project Title

**Northstar Autonomous Analytics and Insight Copilot**  
*(Agentic analytics system: plain-language business questions → verified SQL → plain-language insight with query exposure over the Olist e-commerce dataset)*

**Short name:** Northstar Insight Copilot  

---

## 2. Names of All Team Members

| # | Name | GitHub / identity (from commit history) | Primary focus |
|---|------|----------------------------------------|---------------|
| 1 | **Ankit** | `ankit-2244` | Product & discovery (Sprint 0 docs) |
| 2 | **Vishal** | `vicodwer` | Design, data/sandbox, core agent pipeline (Sprints 1–2) |
| 3 | **Shanmuk** | `ShanmukYadav` | Scale, gateway, full agent set, operate & present (Sprints 3–4) |

**Squad size:** 3  

*Contributions below are aligned with **git commit history on `main`**, not only role labels.*

---

## 3. Sprint Updates

| Sprint | Focus (per project brief) | Status | Led in git (author) |
|--------|---------------------------|--------|---------------------|
| **Sprint 0** | Discover & Define | **Complete** | Ankit |
| **Sprint 1** | Design & De-risk | **Complete** | Vishal |
| **Sprint 2** | Build the Core | **Complete** | Vishal |
| **Sprint 3** | Harden, Scale, Optimize | **Complete** | Shanmuk |
| **Sprint 4** | Verify, Operate, Present | **Complete** | Shanmuk |

### Sprint 0 — Discover & Define *(Ankit)*
- Discovery brief, personas, probing questions  
- PRD v1 (problem, scope, metrics, NFRs)  
- Evaluation plan, risk register v1, team charter  

**Commit:** `docs(sprint-0): discover and define — discovery brief, PRD, eval plan, charter, risk register v1`  
**Evidence:** `docs/prd.md`, `docs/stage1_discover/`, `docs/stage2_define_evalplan/`, `docs/stage4_risk/`, `docs/team_charter.md`

### Sprint 1 — Design & De-risk *(Vishal)*
- Architecture, orchestration decision, agent contracts, verifier contract  
- DuckDB sandbox + data fetch script  
- Synthetic data pipeline, golden set seed, eval harness  
- Riskiest-assumption spike (Verifier)  

**Commit:** `feat(sprint-1): design and de-risk — architecture, contracts, sandbox, synthetic data, golden set, spike`  
**Evidence:** `docs/stage3_design/`, `src/sandbox/`, `src/synthetic/`, `src/spike/`, `evals/`

### Sprint 2 — Build the Core *(Vishal)*
- Live agents: Router, Query Writer, Verifier, Narrator  
- End-to-end pipeline with retry-once  
- First eval scripts (router, query writer, full pipeline)  

**Commit:** `feat(sprint-2): build core path — Router, Query Writer, Verifier, Narrator, pipeline, first evals`  
**Evidence:** `src/agents/`, `src/verifier/`, `src/pipeline.py`, `src/eval/eval_*.py`

### Sprint 3 — Harden, Scale, Optimize *(Shanmuk)*
- LLM gateway, cache, agent registry  
- Clarifier + Planner agents  
- Semantic result matching, regression tests  
- A/B narrator harness, burst load, DSPy/prompt scaffold  

**Commit:** `feat(sprint-3): harden and scale — gateway, Clarifier, Planner, cache, eval semantic match, A/B, burst, close-out`  
**Evidence:** `src/gateway/`, `src/registry/`, `src/agents/clarifier.py`, `src/agents/planner.py`, `tests/`, `src/eval/ab_narrator.py`, `burst_load.py`, `result_match.py`

### Sprint 4 — Verify, Operate, Present *(Shanmuk)*
- FastAPI + web UI  
- Ops runbook, SLOs, canary/rollback  
- Baseline benchmark vs single-LLM path  
- Presentation script, viva prep, close-out docs  

**Commit:** `feat(sprint-4): operate and verify — FastAPI UI, runbook/SLOs, baseline benchmark, handover and presentation materials`  
**Evidence:** `src/api/`, `ops/`, `docs/sprint4/`, `src/eval/baseline_benchmark.py`

### Quality snapshot (system)
| Metric | Value |
|--------|--------|
| Pipeline accuracy (golden set) | **18/18 (100%)** semantic match |
| Avg cost / question | ~**$0.003** |
| Latency p50 / p95 (sequential) | ~**5.5s / 8.4s** |
| Burst (10 concurrent) | 10/10 answered |

---

## 4. Latest Project Status

| Dimension | Status |
|-----------|--------|
| **Overall** | **Sprints 0–4 complete** |
| **Demo** | Local FastAPI UI working (`uvicorn src.api.app:app --port 8000`) |
| **Core quality** | Golden-set **18/18**; clarify & refuse behaviors working |
| **Data** | Olist in DuckDB (read-only); rebuild via `python src/sandbox/build_db.py` |
| **Cloud** | Docker/AWS pilot planned next (college budget ≤ ₹2000) |
| **Presentation** | Script ready: `docs/sprint4/presentation_20min.md` |

### Runtime architecture

```
User (UI / API)
  → FastAPI
  → LLM Gateway
  → Router → (refuse | Clarifier | Planner | standard path)
  → Query Writer → Verifier (retry-once) → Narrator
  → Answer + SQL shown + cost/latency
```

### How to run

```text
1. Clone the GitHub repository
2. Create .env with OPENROUTER_API_KEY=...
3. pip install -r requirements.txt
4. python src/sandbox/build_db.py   # if sandbox.duckdb missing
5. uvicorn src.api.app:app --host 0.0.0.0 --port 8000
6. Open http://localhost:8000/
```

---

## 5. Individual Contribution of Each Team Member

*(Based on git authors and files in each sprint commit.)*

### Ankit (`ankit-2244`)
| Area | Contribution |
|------|----------------|
| Product / discovery | Discovery brief, personas, problem framing |
| PRD | Problem statement, users, scope, metrics, NFRs |
| Planning | Evaluation plan, risk register v1, team charter |
| Sprint ownership | **Sprint 0** commit |

### Vishal (`vicodwer`)
| Area | Contribution |
|------|----------------|
| Architecture | Architecture doc, orchestration decision record, agent contracts, verifier contract |
| Data | Sandbox builder, synthetic generators, golden/synthetic sets, fetch script |
| Core system | Router, Query Writer, Narrator, Verifier checks, end-to-end pipeline |
| Eval (core) | `eval_pipeline`, `eval_query_writer`, `eval_router`, golden-set fixes |
| De-risk | Riskiest-assumption spike |
| Sprint ownership | **Sprint 1** and **Sprint 2** commits |

### Shanmuk (`ShanmukYadav`)
| Area | Contribution |
|------|----------------|
| Scale / platform | LLM gateway, response/question cache, agent registry |
| Full agent set | Clarifier, Planner; hardened query/eval matching |
| Quality harnesses | Semantic `result_match`, pytest suite, A/B narrator, burst load, DSPy scaffold |
| Operate | FastAPI API + UI, runbook, SLOs, canary/rollback |
| Verify / present | Baseline benchmark, presentation script, viva prep, Sprint 4 status/close-out |
| Sprint ownership | **Sprint 3** and **Sprint 4** commits |

---

## 6. Collective / Team Contribution

As one squad, the team jointly delivered:

1. End-to-end **agentic analytics copilot** on real multi-table Olist data  
2. Full lifecycle artifacts: discover → define → design → risk → data → build → harden → operate  
3. Safety behaviors: clarify ambiguous questions, refuse destructive intent, deterministic SQL verification  
4. Measured quality and cost (golden set, cost/latency, burst helper)  
5. Pilot operate surface: API + UI + ops docs  
6. Defense materials: presentation script and viva prep  
7. Shared standards: one repository, secrets kept out of git, offline unit tests for critical logic  

---

## 7. GitHub Repository Link

**Repository:**  
https://github.com/ShanmukYadav/Northstar-Copilot  

**Default branch:** `main`  

### Repository contents checklist

| Required item | Location |
|---------------|----------|
| Source code | `src/` |
| Documentation | `docs/` (including this file) |
| Datasets | Olist via rebuild path / local `data/` (large raw CSVs may be local-only; rebuild documented) |
| APIs | FastAPI in `src/api/app.py` (LLM via OpenRouter; no custom fine-tuned weights) |
| Presentation / reports | `docs/sprint4/presentation_20min.md`, `docs/FINAL_SUBMISSION.md` |
| Other | `ops/`, `evals/`, `tests/`, `requirements.txt`, `README.md` |

**Never commit** `.env` or API keys.

---

## 8. Declaration

We confirm that this submission describes Sprints 0–4 on the Northstar Insight Copilot, that the GitHub repository is the source of truth for code and documentation, and that secrets are not stored in the repository.

| Role | Name | Signature / Date |
|------|------|------------------|
| Team member | Ankit | ________________ |
| Team member | Vishal | ________________ |
| Team member | Shanmuk | ________________ |

---

*Final submission · Project 05 · Northstar Autonomous Analytics and Insight Copilot · Team of 3 (Ankit, Vishal, Shanmuk)*
