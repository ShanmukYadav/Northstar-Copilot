# Sprint 3 — Harden, Scale, Optimize

**Baseline:** Sprint 2 complete (core path Router → Query Writer → Verifier → Narrator, first eval/cost baseline).  
**Brief exit criteria:** Full agent set · concurrency and caching · A/B and DSPy results · regression suite · updated risk register.

## Priority order (this sprint)

| # | Work item | Brief mapping | Status |
|---|-----------|---------------|--------|
| 1 | LLM gateway (single call path, routing, retries, cost) | Stage 6 gateway live | **Done** (`src/gateway/`) |
| 2 | Agent registry (versioned JSON) | Stage 3/6 registry operational | **Done** (`src/registry/`) |
| 3 | Clarifier + Planner agents | Full agent set | **Done** |
| 4 | Pipeline rewire (clarify path, plan path, gateway, cache) | Core topology E2E | **Done** |
| 5 | Exact-match response + question cache | Bursty load / cost | **Done** (exact-match; semantic later) |
| 6 | Concurrent question runner (burst helper) | Handle bursty load | **Done** (measure with `burst_load.py`) |
| 7 | Regression suite (pytest) | Stage 7 regression | **Done** (`tests/`) |
| 8 | Narrator A/B harness (cheap vs strong tier) | A/B results | **Harness ready** — run to produce numbers |
| 9 | DSPy / prompt-variant before-after | DSPy before/after | **Harness ready** — run to produce numbers |
| 10 | Risk register Sprint 3 update | Exit criterion | **Done** (addendum) |

## Known Sprint 2 gaps carried in

- Gateway was design-only — **closing this sprint**.
- Clarifier / Planner not built — **closing this sprint**.
- No concurrency/caching — **closing this sprint**.
- Golden set still thin (18 items) — enlarge in Stage 5/7; regression runs on what we have.
- RAGAS / calibrated judge / full deploy — Stage 7/8, not all of Sprint 3.

## Done looks like (Sprint 3)

- Every model call goes through `src/gateway/`.
- Ambiguous questions get a real clarifying question (not a generic stop).
- Comparative questions can take a multi-step plan path.
- Repeated questions hit cache; concurrent runner exists for 20-way burst measurement.
- `pytest` regression covers verifier + cache + registry; eval script remains the live LLM gate.
- Risk register addendum documents what is mitigated vs residual.
