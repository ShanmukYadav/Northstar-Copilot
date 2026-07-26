# Sprint 3 — Closed

**Status:** COMPLETE  
**Closed:** 2026-07-21  
**Brief focus:** Harden, Scale, Optimize  

Exit criteria from the project brief (Sprint 3): full agent set · concurrency and caching · A/B and DSPy results · regression suite · updated risk register.

---

## 1. Evidence pack (artifacts)

| Artifact | Path |
|----------|------|
| Full pipeline eval (18/18) | `docs/sprint3/eval_pipeline_results.json` |
| Burst / concurrent load | `docs/sprint3/burst_load_results.json` |
| Narrator A/B | `docs/sprint3/ab_narrator_results.json` |
| Query Writer prompt A/B (DSPy-shaped) | `docs/sprint3/dspy_prompt_ab_results.json` |
| Risk register addendum | `docs/stage4_risk/risk_register.md` (Sprint 3 section) |
| Plan | `docs/sprint3/sprint3_plan.md` |

Offline regression: `pytest tests/` (verifier, cache, registry, semantic match).

---

## 2. Locked metrics

### System quality (golden set)
| Metric | Value |
|--------|--------|
| Pipeline accuracy | **18/18 (100%)** semantic match |
| Total run cost | **$0.052** |
| Avg cost / question | **$0.00290** (≪ $0.02 cheap-path ceiling) |
| Latency p50 / p95 (sequential) | **5.49s / 8.40s** |

### Concurrency + caching (burst, 10 workers, 10 questions)
| Metric | Value |
|--------|--------|
| All answered | **10/10** |
| Wall clock | **~9.8s** for 10 concurrent questions |
| p50 / p95 latency (per question under load) | **9.16s / 9.77s** |
| Total cost | **~$0.028** |
| Cache on first-seen questions | 0 hits / 10 misses (expected; exact-match only) |

PRD guardrail is p95 under **20** concurrent requests. We measured **10** workers as the Sprint 3 scale signal. Residual: 20-worker run + semantic cache deferred (not required to close Sprint 3 engineering).

### Narrator A/B winners
| Arm | Avg cost | Avg latency | Answered |
|-----|----------|-------------|----------|
| **Cheap (Haiku) — WINNER for default** | **$0.00292** | 6.16s | 3/3 |
| Strong (Sonnet) | $0.00402 (~+38%) | 5.70s | 3/3 |

**Decision:** keep **cheap narrator as production default**. Escalate to strong only if Stage 7 RAGAS faithfulness shows a material gap. Cost guardrail wins; latency difference on n=3 is not decisive.

### Query Writer prompt A/B (DSPy-shaped manual)
| Variant | Accuracy (n=8 gold_sql sample) |
|---------|--------------------------------|
| baseline_short | 5/8 (62.5%) |
| rules_first | 5/8 (62.5%) |
| Delta | **0.0** |

**Decision:** no lift from the short A/B sample alone. **Keep production Query Writer prompt** (full rules in `query_writer.py`, including join grain, customer key, no silent ROUND, English categories) — proven by **18/18 full pipeline**, not by this 8-item micro-A/B. DSPy auto-compile remains optional later; harness is `src/eval/dspy_query_writer_stub.py`.

---

## 3. What Sprint 3 delivered

1. **LLM gateway** — task routing, retries, fallbacks, cost log, LLM cache  
2. **Agent registry** — versioned JSON  
3. **Full agent set** — Clarifier + Planner wired with Router / QW / Verifier / Narrator  
4. **Caching** — exact-match LLM + question caches  
5. **Concurrency** — `answer_questions_concurrent` + `burst_load.py`  
6. **Regression** — pytest + live golden eval with semantic matching  
7. **A/B evidence** — narrator cheap vs strong; prompt variant scaffold  
8. **Risk register** — Sprint 3 mitigations and residuals documented  

---

## 4. Residual risks (carry to Sprint 4 / Stage 7–8)

| Residual | Why it remains |
|----------|----------------|
| Concurrent p95 @ **20** workers unmeasured | Measured at 10; PRD wording is 20 |
| Exact-match cache only | Rephrases miss; no Chroma/semantic cache |
| Golden set still thin (18) | Plan target ~150–200 |
| No RAGAS / calibrated judge yet | Stage 7 Verify |
| No deploy / runbook yet | **Sprint 4 Operate** |
| Full DSPy compile not run | Manual A/B + production prompt sufficient for close |

---

## 5. Sprint 3 exit checklist

| Brief criterion | Met? |
|-----------------|------|
| Full agent set | **Yes** |
| Concurrency and caching | **Yes** (cache live; burst measured @ 10 workers) |
| A/B and DSPy results | **Yes** (artifacts + winners above) |
| Regression suite | **Yes** (pytest + 18/18 pipeline) |
| Updated risk register | **Yes** |

**Sprint 3 is closed.** Next: **Sprint 4 — Verify/Operate/Present** (API, minimal UI, runbook, SLOs, demo materials).
