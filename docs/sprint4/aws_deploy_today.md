# AWS deploy — same day runbook

**Budget:** ≤ ₹2,000 (IITGN). Prefer t3.micro, stop when idle.  
**Region:** `ap-south-1` (Mumbai) recommended.  
**LLM cost:** OpenRouter is separate from AWS bill.

---

## A. Local package check (laptop)

```powershell
cd C:\Users\autumn\OneDrive\Desktop\northstar-copilot

# .env must exist with OPENROUTER_API_KEY (never commit)
# data/sandbox.duckdb should exist (or data/olist_raw for rebuild)

docker compose build
docker compose up -d
curl http://127.0.0.1:8000/ready
# Browser: http://127.0.0.1:8000/
docker compose down
```

---

## B. AWS console (you click)

1. Billing → Budget → alerts at ₹500 / ₹1000 / ₹1500.  
2. EC2 → Launch instance:  
   - Name: `northstar-copilot`  
   - AMI: Ubuntu 22.04  
   - Type: **t3.micro** (or free-tier micro)  
   - Key pair: create/download `.pem`  
   - Storage: 20 GB  
   - Security group:  
     - SSH 22 → **My IP**  
     - Custom TCP **8000** → **0.0.0.0/0** (public UI today)  
3. Launch → copy **Public IPv4**.

---

## C. Server setup (SSH)

```bash
# From your laptop (Git Bash / WSL / PowerShell with OpenSSH)
ssh -i path/to/key.pem ubuntu@PUBLIC_IP

sudo apt-get update
sudo apt-get install -y git curl ca-certificates
# Docker official install (Ubuntu):
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker ubuntu
# log out and back in for docker group, or use sudo docker

git clone https://github.com/ShanmukYadav/Northstar-Copilot.git
cd Northstar-Copilot
# If Docker files not on remote yet, scp them from laptop (see section E)

nano .env
# paste: OPENROUTER_API_KEY=sk-or-...
# save

# Option 1: copy DB from laptop (faster if CSVs large)
# (from laptop, new terminal)
# scp -i key.pem data/sandbox.duckdb ubuntu@PUBLIC_IP:~/Northstar-Copilot/data/

# Option 2: build on server if olist_raw present
mkdir -p data
# scp -i key.pem -r data/olist_raw ubuntu@PUBLIC_IP:~/Northstar-Copilot/data/

docker compose up -d --build
curl http://127.0.0.1:8000/ready
```

Public check from laptop:

```text
http://PUBLIC_IP:8000/ready
http://PUBLIC_IP:8000/
```

---

## D. Latency test (from laptop)

```powershell
cd C:\Users\autumn\OneDrive\Desktop\northstar-copilot
python scripts/latency_test.py --base-url http://PUBLIC_IP:8000 --n 12 --concurrency 5 --concurrent-n 10
```

Results: `docs/sprint4/aws_latency_results.json`

---

## E. If GitHub missing Docker files

From laptop (while SSH works):

```powershell
cd C:\Users\autumn\OneDrive\Desktop\northstar-copilot
scp -i path\to\key.pem Dockerfile docker-compose.yml .dockerignore ubuntu@PUBLIC_IP:~/Northstar-Copilot/
scp -i path\to\key.pem -r docker ubuntu@PUBLIC_IP:~/Northstar-Copilot/
scp -i path\to\key.pem requirements.txt ubuntu@PUBLIC_IP:~/Northstar-Copilot/
scp -i path\to\key.pem -r src ubuntu@PUBLIC_IP:~/Northstar-Copilot/
```

Or push to GitHub then `git pull` on server.

---

## F. User testing (same day)

1. Share `http://PUBLIC_IP:8000/` + `docs/sprint4/user_testing_protocol.md`  
2. 5–10 users, 10–15 min each  
3. Collect form responses  
4. Write short notes in `docs/sprint4/aws_user_testing_report.md`  

---

## G. End of day

```bash
# on server optional: docker compose down
```

**EC2 console → Stop instance** (do not terminate if you need it tomorrow; stop saves most compute cost).

---

## Smoke checklist

| Check | Pass |
|-------|------|
| /ready | 200 |
| Unique customers | answered |
| Why sales down | needs_clarification |
| Update price… | refused |
| Latency JSON written | yes |
| Users ≥5 | yes |
| Instance stopped after | yes |
