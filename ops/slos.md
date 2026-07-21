# Service Level Objectives — Northstar Insight Copilot (v1 pilot)

Sprint 4 · grounded in PRD section 6 + Sprint 3 measured baselines.

## SLOs

| SLO | Target | Measurement | Sprint 3 baseline |
|-----|--------|-------------|-------------------|
| **Availability** | ≥ 99% of `/ready` probes succeed during demo window | HTTP GET `/ready` every 1 min | N/A (local pilot) |
| **Latency (single request)** | p95 ≤ 15s for standard answered questions | `latency_seconds` on `/ask` | p95 **8.4s** sequential golden run |
| **Latency (burst)** | p95 ≤ 20s under 10 concurrent (pilot) | `burst_load.py` | p95 **~9.8s** @ 10 workers |
| **Execution quality** | ≥ 90% on locked golden set | `eval_pipeline.py` | **100% (18/18)** |
| **Cost ceiling** | ≤ $0.02 / answered question (cheap path) | `cost_usd` on `/ask` | **~$0.0029** avg |
| **Safety floor** | Ambiguous → clarify; destructive → refuse | Golden items gs014–016 | **Pass** |

## Alerts that protect SLOs

| Condition | Action |
|-----------|--------|
| `/ready` down > 2 min | Page operator; restart / fix key or DB |
| p95 latency > 20s over 10 requests | Check OpenRouter; reduce concurrency; enable cache for demos |
| Cost / question > $0.015 average | Inspect model routing; force cheap narrator |
| Golden-set regression < 90% | Block model/prompt promote; rollback |

## Non-goals for v1 pilot

- Multi-region HA  
- Automatic horizontal scale  
- Full OpenTelemetry stack (use `/metrics` + logs)
