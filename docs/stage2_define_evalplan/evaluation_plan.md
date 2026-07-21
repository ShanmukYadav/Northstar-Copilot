# Evaluation Plan v1
Sprint 0 deliverable - full harness build lands in Sprint 1, deepens in Sprint 3 (Stage 7)
Owner: Anvay (drives) - Reviewer: Vishal

This is a **plan**, not the harness itself -- it exists so Sprint 0 can close with a
concrete answer to "how will we know if this works," before any agent code is written.

## 1. What we're measuring, and against what

Every metric in this plan maps directly to a PRD section 6 target -- nothing measured here that
isn't traceable back to a north-star, supporting, or guardrail metric.

| PRD metric | How it's measured | Tooling |
|---|---|---|
| Execution accuracy (north-star) | Golden-set questions run through the system; result compared to gold result set (exact match on rows/aggregates, not string match on SQL -- two different correct queries should both pass) | Custom harness + golden set |
| Insight faithfulness (supporting) | Does the Narrator's explanation only state facts present in the verified result? | RAGAS faithfulness metric |
| Ambiguity-handling floor (guardrail) | % of adversarial ambiguous questions that trigger Clarifier, not a guess | Custom harness, labeled adversarial subset |
| Latency (guardrail) | p95 end-to-end time under the stated 20-concurrent-request burst load | Load-test harness (Stage 6/7) |
| Cost per question (guardrail) | $ per successfully answered question, gateway-logged, split by cheap/escalated path | LiteLLM gateway cost logs |

## 2. Golden set design

- **Source**: real, labeled data plus curated correct outputs, per the brief's "Build a
  golden set from real labeled data plus curated correct outputs" (p.7) -- built from the
  real Olist schema (Stage 2 profiling), not invented questions.
- **Composition** (target ~150-200 questions for v1, scaled up in Stage 5):
  - Plain-language questions paired with gold SQL, across difficulty levels (simple
    lookup to aggregation to trend to comparative), weighted toward the Stage 1 volume
    estimates (section 2 of discovery brief) so the set reflects real usage, not a uniform
    academic split.
  - **Ambiguous/underspecified questions** (labeled as such) -- used to score the
    ambiguity-handling guardrail specifically, not execution accuracy.
  - **Adversarial questions** that tempt the two canonical wrong-join/wrong-key cases
    identified in Stage 2 (order-item join-grain, `customer_id` vs.
    `customer_unique_id`) plus other schema-specific traps found during Stage 5 EDA.
  - **Rare-schema-corner questions** -- deliberately touching low-volume categories/tables
    to check the system doesn't only work on the well-trodden 80%.
- **Locked and versioned** once built (Stage 5/6) -- it becomes the regression gate for
  every subsequent change (brief p.7, "run it as a regression suite on every change").

## 3. Baseline methodology (closing the PRD's "TBD" gap)

Rather than leave execution accuracy's baseline as an unmeasured "TBD," we anchor it to
published reference points, clearly labeled as a **projection**, to be replaced with a
measured number once the golden set + a naive single-LLM path both exist (Sprint 1-2):

- Published BIRD-benchmark zero-shot single-LLM execution accuracy for strong frontier
  models sits roughly in the **40-55% range** without agentic scaffolding (e.g. GPT-4
  zero-shot approx 45-48%, per BIRD leaderboard data), while heavily agentic pipelines with
  verification reach **74-82%**.
- Our task is narrower than BIRD's cross-domain 95-database setting -- single, well-known
  schema, retrieval-grounded -- so a naive single-LLM baseline on *our* golden set is
  projected somewhat higher than the raw BIRD zero-shot number, but meaningfully below
  our verified-pipeline target.
- **Projected baseline: ~55-65% execution accuracy for a naive single-LLM-no-verification
  path**, ~90% target for our full verified pipeline. This projection, not the target,
  is what gets replaced with a real measured number in Sprint 2 once the core path runs
  (brief's "Run an end-to-end benchmark against a single-LLM baseline," p.7 -- that's the
  real measurement; this is the placeholder that makes the PRD judgeable until then).

## 4. LLM-as-judge, calibrated

- Written rubric scoring: does the answer match the gold result, is the explanation
  faithful to the verified data, does the query's logic match the question's intent
  (not just its literal wording).
- **Calibration**: a human-labeled sample (target: 30-50 questions, cross-reviewed by at
  least 2 team members per the charter's cross-review agreement) scored independently by
  the judge; report agreement rate (e.g. Cohen's kappa or simple % agreement) before
  trusting the judge on the full golden set. If agreement is weak, the rubric gets
  revised before the judge is used for regression gating -- an uncalibrated judge is not
  used to make ship/no-ship decisions.

## 5. RAGAS scope

Faithfulness, answer relevancy, and context precision/recall (brief p.7) -- applied to
the Narrator's explanation against the Verifier's `result_summary` and the retrieved
schema context, not against the raw database. This directly operationalizes "insight
faithfulness" from the PRD, so it isn't just a supporting metric in name only.

## 6. A/B and DSPy (planned scope, executed in Sprint 3)

- A/B candidates already visible from Stage 3 decisions worth testing empirically rather
  than assuming: retry-once vs. retry-zero on Verifier failure; Haiku vs. Sonnet on the
  Narrator for the cheap path (cost/faithfulness tradeoff flagged in the routing table).
- DSPy optimizes the Query Writer and Narrator prompts against execution accuracy and
  faithfulness respectively -- before/after reported honestly, including regressions.

## 7. Safety / red-team pass (planned scope)

Run the adversarial subset of the golden set (join-grain traps, ambiguous questions,
out-of-scope/destructive-intent prompts) specifically against the Router's refusal
behavior and the Verifier's catch rate -- this is where risk register items #1, #2, #6,
#7 get their residual-risk claims actually tested, not just asserted.

## 8. What this plan does not cover yet

- Concrete pass/fail thresholds for the confidence-signal escalation trigger (PRD section 7 open
  item) -- set once golden-set results exist, not guessed here.
- The exact 20-concurrent-request burst-load test harness -- belongs to Stage 6/7 build,
  not this plan.
