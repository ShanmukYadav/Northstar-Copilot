# Northstar Insight Copilot — Operate Runbook

Sprint 4 · Stage 8 Operate  
Audience: whoever is on call for the demo / pilot API.

---

## 1. What is running

| Piece | Location |
|-------|----------|
| API + UI | `uvicorn src.api.app:app --host 0.0.0.0 --port 8000` |
| Pipeline | `src/pipeline.py` |
| Sandbox DB | `data/sandbox.duckdb` (built from `data/olist_raw/`) |
| Secrets | `.env` → `OPENROUTER_API_KEY` only (never commit) |

---

## 2. Start / stop

```powershell
cd northstar-copilot
# one-time
pip install -r requirements.txt
python src\sandbox\build_db.py   # if sandbox.duckdb missing

# run
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

- UI: http://localhost:8000/  
- Health: http://localhost:8000/health  
- Ready: http://localhost:8000/ready  
- Metrics: http://localhost:8000/metrics  
- Docs: http://localhost:8000/docs  

Stop: Ctrl+C in the terminal.

---

## 3. Monitoring (lightweight)

| Signal | Where | Healthy |
|--------|--------|---------|
| Process up | `/health` → `status: ok` | HTTP 200 |
| Dependencies | `/ready` | HTTP 200; sandbox + API key |
| Traffic mix | `/metrics` → `requests` | answered rising; errors near 0 |
| Cost | `/metrics` → `gateway_cost.total_cost_usd` | Under budget alarm (see SLOs) |
| Cache | `/metrics` → `question_cache` / `llm_cache` | Hits rise on repeat Qs |

There is no external APM in v1. For a demo/pilot, poll `/metrics` or watch the uvicorn log.

---

## 4. Alerts (manual thresholds)

Trigger investigation if:

1. **`/ready` fails** for > 2 minutes (DB missing or key missing).  
2. **Error rate** (`errors / total`) > 10% over 20 requests.  
3. **Cost** process total climbs faster than ~$0.02 × expected questions (see SLOs).  
4. **Latency**: user reports > 20s single question repeatedly (Sprint 3 p95 was ~8–10s).  
5. **Escalate rate** spikes — Verifier failing often; check OpenRouter / schema drift.

---

## 5. Human fallback path (Devon)

When the API returns:

| Status | Meaning | Operator action |
|--------|---------|-----------------|
| `needs_clarification` | Ambiguous question | User answers clarifier; or route ticket to analyst with the clarifying question |
| `escalate` | Could not verify SQL | Forward question + any `sql_shown` / failure from logs to analyst queue |
| `refused` | Out of scope / write intent | No data change; explain read-only policy |
| `500` | System fault | Check `/ready`, OpenRouter status, restart uvicorn |

Never re-run a failed question by disabling the Verifier.

---

## 6. Rollback

### Prompt / model change went bad

1. Revert the agent file or gateway `TASK_ROUTING` to last known good git commit.  
2. Restart uvicorn.  
3. Smoke: `POST /ask` with “How many unique customers do we have?” → expect `answered` + SQL.  
4. Run offline: `pytest tests/ -q`.  

### Bad deploy / broken env

1. Stop the process.  
2. Restore previous `.env` only if rotated incorrectly (keys).  
3. Rebuild DB if corrupted: `python src/sandbox/build_db.py`.  
4. Restart API; hit `/ready`.

### Kill switch (product)

If answers are systematically wrong: stop taking traffic (stop API) and set a status message; do not “turn off verifier.”

---

## 7. Cost alarms

- Sprint 3 baseline: ~**$0.003 / successful question** on cheap path.  
- Ceiling (PRD): **$0.02** cheap path.  
- Alarm: average cost over last N questions (from logs/`/metrics`) **> $0.015** → check if strong narrator or Sonnet fallback is firing (`fallback_used` in gateway cost log).

---

## 8. Incident response (short)

1. **Detect** — `/ready` red, user report, or cost spike.  
2. **Contain** — stop API if wrong answers in production; otherwise fix forward.  
3. **Diagnose** — uvicorn traceback, `/metrics`, OpenRouter dashboard.  
4. **Mitigate** — restart, restore model routing, rebuild DB.  
5. **Verify** — smoke `/ask` + optional `python src/eval/eval_pipeline.py` if quality suspect.  
6. **Note** — one paragraph in risk register or sprint log.

---

## 9. On-call checklist (demo day)

- [ ] `.env` has `OPENROUTER_API_KEY`  
- [ ] `data/sandbox.duckdb` exists  
- [ ] `uvicorn` running; `/ready` 200  
- [ ] One happy path + one clarify + one refuse tested in UI  
- [ ] Know how to Ctrl+C and restart in < 1 minute  
