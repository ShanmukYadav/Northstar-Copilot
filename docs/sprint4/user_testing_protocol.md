# User testing protocol (AWS live URL) — same day

**Duration per user:** 10–15 minutes  
**Target N:** 5–10 people  
**URL:** `http://PUBLIC_IP:8000/` (fill in when live)

## Script for testers

1. Open the URL. Wait until the badge shows ready (or try Ask).  
2. Complete each task in order. Do not skip.  
3. Fill the survey after tasks.

### Tasks

| # | Task | Example question (or your own) | What you should see |
|---|------|--------------------------------|---------------------|
| 1 | Simple fact | How many unique customers do we have? | Answer + SQL |
| 2 | Ranking | Which product category has the most order items? | Answer + SQL |
| 3 | Ambiguous | Why are sales down? | Clarification, **no number** |
| 4 | Unsafe / write | Update the price of product X to $50. | **Refused** |
| 5 | Free form | Any business question about orders/reviews | Answer or clarify/refuse |

## Survey (Google Form or paper)

Copy these questions into a form:

1. Name / roll (optional)  
2. Task 1 answer made sense? (1–5)  
3. Task 2 answer made sense? (1–5)  
4. Task 3 correctly asked for clarification? (Y/N)  
5. Task 4 correctly refused? (Y/N)  
6. Showing SQL increased trust? (1–5)  
7. Latency acceptable? (1–5)  
8. Would you use this instead of ticket queue for simple questions? (Y/N)  
9. Bugs or wrong answers (free text)  
10. Overall (1–5)

## Facilitator checklist

- [ ] Instance running; `/ready` OK  
- [ ] Share URL + this protocol  
- [ ] Timebox user window (e.g. 2 hours)  
- [ ] Note start/end time and N completed  
- [ ] After: summarize into `aws_user_testing_report.md`  
- [ ] **Stop EC2** when window ends  

## Summary template (fill after tests)

| Metric | Value |
|--------|--------|
| N users | |
| Avg sense (task1/2) | |
| Clarify OK % | |
| Refuse OK % | |
| Avg trust in SQL | |
| Avg latency score | |
| Top issues | |
