# Sprint 4 readiness gate

## Major flaw fixed: gs004 Portuguese vs English category

**Symptom:** gold `bed_bath_table` / 11115 vs got `cama_mesa_banho` / 11115 — same category and count, different language label.

**Fixes:** semantic matcher treats `category_translation` PT↔EN as equal; Query Writer rule 10 prefers English via `category_translation` for user-facing category answers.

## Major flaw fixed: gs010-class false failures

**Symptom (Sprint 3 eval):** 17/18 (94%). `gs010` FAIL with:

```
gold=[('RJ', 15.237…), ('SP', 8.700…)]
got =[('RJ', 15.24, 12350), ('SP', 8.7, 40494)]
```

**Root cause (not a wrong delivery-time metric):**
1. Eval used **exact tuple equality** — `ROUND` and an extra `COUNT` column failed the grade even though averages matched.
2. Query Writer had no rule against silent `ROUND` / extra context columns.
3. Planner could over-split simple SP-vs-RJ comparisons.

**Fixes landed:**
| Area | Change |
|------|--------|
| `src/eval/result_match.py` | Semantic match: float tol 0.05, gold values subset of got row |
| `src/eval/eval_pipeline.py` | Uses semantic match; multi-step SQL; **caches off**; writes JSON report |
| `src/eval/eval_query_writer.py` | Same matcher |
| `src/agents/query_writer.py` | Rules 7–9: no silent ROUND, only requested columns, prefer one GROUP BY |
| `src/agents/planner.py` | SP/RJ one-metric → single step |
| `tests/test_result_match.py` | Locks gs010 case + regressions |

## Re-verify before Sprint 4 build

```powershell
cd C:\Users\autumn\OneDrive\Desktop\northstar-copilot\northstar-copilot
python -m pytest tests\ -q
python src\eval\eval_pipeline.py
```

**Exit bar for “ready for Sprint 4”:**
- Offline tests green
- Pipeline accuracy **≥ 17/18**, target **18/18** after re-run
- `docs/sprint3/eval_pipeline_results.json` written
- No open P0: wrong answer graded as pass (semantic matcher still fails wrong avgs/states)

## Sprint 4 scope (Operate) — start only after re-run

From the project brief Stage 8 / Sprint 4:
- Deploy API + minimal UI (FastAPI)
- Operate runbook (monitoring, fallback, rollback, on-call, cost alarms)
- SLOs + canary/rollback for prompt/model changes
- Presentation / Demo Day materials

Not required to *start* Sprint 4, but track as residual: concurrent p95 at 20 workers, RAGAS, full DSPy compile, Chroma retrieval.
