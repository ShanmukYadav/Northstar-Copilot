# Northstar Autonomous Analytics and Insight Copilot

Agentic analytics: natural-language questions over **Olist** → verified SQL → plain-language answer (SQL shown).

**Repo:** https://github.com/ShanmukYadav/Northstar-Copilot  

## Quick start (local)

```powershell
cd northstar-copilot
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
# .env with OPENROUTER_API_KEY=...
python src/sandbox/build_db.py   # if data/sandbox.duckdb missing
uvicorn src.api.app:app --host 0.0.0.0 --port 8000
```

UI: http://localhost:8000/

## Docker

```powershell
# Docker Desktop must be running
# .env + data/sandbox.duckdb (or data/olist_raw/)
docker compose up --build -d
```

## Same-day AWS

See **`docs/sprint4/aws_deploy_today.md`**.

```text
1. Budget alerts (₹500 / 1000 / 1500)
2. EC2 t3.micro Ubuntu, SG: 22=your IP, 8000=public
3. Install Docker, clone repo, .env with key, mount data
4. docker compose up -d --build
5. Latency: python scripts/latency_test.py --base-url http://PUBLIC_IP:8000
6. User test: docs/sprint4/user_testing_protocol.md
7. STOP the instance when done
```

## Layout

- `src/` agents, gateway, pipeline, API  
- `ops/` runbook, SLOs  
- `docs/` PRD, design, sprint materials  
- `evals/` golden set  
- `tests/` offline regression  
