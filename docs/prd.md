# PRD -- Northstar Insight Copilot
Stage 2 - Define - v1
Owner: Ankit (drives) - Reviewer: Shanmuk

## 1. Problem statement

Northstar's business users can't query their own data. Every question -- "which category
sells best," "why did reviews drop," "how many orders shipped late" -- routes through a
small analyst team via ticket queue. The backlog is long, most questions are simple
enough to answer directly, and analysts are spent on repetitive lookups instead of hard
problems. Worse: when a tool *does* try to automate this today, a wrong query returns a
confident, wrong number, and nobody downstream can tell the difference between a right
answer and a wrong one dressed up the same way.

## 2. Target users (finalized personas -- see Stage 1 for full detail)

| Persona | Job to be done |
|---|---|
| Priya, Regional Ops Manager | "When I have a business question, get a trustworthy answer without waiting on the analyst queue or learning SQL." |
| Devon, Senior Analyst (escalation) | "Get freed from repetitive lookups so I only handle questions that genuinely need judgment." |
| Sam, Category Manager (power user) | "Explore comparative and trend questions myself, with the query visible so I can sanity-check it." |
| Jordan, Head of Analytics Ops | "Know what every answered question costs and have an audit trail if a number is ever challenged." |

## 3. Real data profile (Olist, measured -- not estimated)

Source: `olist_orders_dataset.csv` + 6 joined tables, pulled from the public Olist
e-commerce release. Full figures in `data/profile_olist.py` output; headline numbers:

- **99,441 orders**, 112,650 order line items, 99,441 customer rows, 3,095 sellers,
  32,951 products across **73 product categories**, spanning **2016-09-04 to 2018-10-17**.
- **Order status is 96.5% "delivered"**; the remainder (shipped, canceled, unavailable,
  invoiced, processing) is where "how many orders X" questions get subtly wrong if the
  agent doesn't filter status explicitly -- this is a concrete ambiguity source, not
  hypothetical.
- **Delivery-date nulls**: 1,783 rows missing `order_delivered_carrier_date`, 2,965
  missing `order_delivered_customer_date`. Any "average delivery time" query must decide
  how to handle these -- a naive AVG() silently drops them, which is exactly the
  "confident wrong answer" failure mode the brief warns about.
- **Join-grain risk, measured**: 9,803 of 98,666 orders (~9.9%) have more than one line
  item, and 1,278 orders involve more than one seller. A query that joins
  orders-to-order_items naively and does `COUNT(order_id)` instead of `COUNT(DISTINCT
  order_id)` will overcount -- this is our canonical "wrong join" adversarial case for
  the synthetic eval set (Stage 5).
- **customer_id vs customer_unique_id**: 99,441 distinct `customer_id` but only 96,096
  distinct `customer_unique_id` -- Olist issues a new `customer_id` per order. Any
  "unique customers" or repeat-purchase question that uses the wrong key is wrong by
  construction. Second canonical adversarial case.
- **Category volume is long-tailed**: top category (bed_bath_table) has 11,115 items;
  the 73-category spread means "which category" questions need a real GROUP BY, not a
  memorized top-N.
- **Review scores are skewed positive** (57,328 five-star of 99,224; only 41.3% carry a
  free-text comment) -- relevant to any "why are reviews down" style question, which
  falls into the ambiguous/no-single-query bucket flagged in Stage 1.
- **Geolocation table was not available** in our data pull (only the 9 e-commerce core
  tables + 2 marketing-funnel bonus tables). Any question requiring seller-to-customer
  distance is **out of scope** for v1 -- logged as a scope exclusion below, not silently
  dropped.

## 4. Scope

**In scope (v1)**
- Natural-language questions over the 7 core Olist tables (orders, order_items,
  order_payments, order_reviews, products, customers, sellers) + category translation.
- The 5 automatable question categories from Stage 1: simple lookup, aggregation/ranking,
  trend/time-series, comparative/multi-entity, and clarification flow for ambiguous
  questions.
- Read-only SQL execution against a sandboxed copy of the data.
- Query exposure -- every answer shows the SQL that produced it.
- Result verification before an answer is returned to the user.

**Out of scope (v1)**
- Any write/update/destructive action, regardless of phrasing.
- Geolocation/distance questions (data not available in this pull).
- Marketing-funnel tables (closed_deals, marketing_qualified_leads) -- different grain,
  different join keys, deferred to a v2 scope decision.
- Free-text review sentiment analysis beyond the numeric review_score.
- Multi-turn conversational memory beyond a single question's clarification exchange.

## 5. Assumptions (marked, since we have no live client to ask)

- The system is read-only; no destructive capability is ever exposed as a tool.
- Ambiguous questions are clarified, never guessed.
- Devon's team (or a designated human) is the escalation path below a confidence
  threshold -- threshold to be set empirically in Stage 7 evaluation, not guessed here.
- Olist's 2016-2018 data is presented to users as a fixed historical dataset, not framed
  as live/current, to avoid misleading a business user about data freshness.

## 6. Target metrics -- north-star, supporting, guardrails

| Metric | Type | Definition | Baseline | Target |
|---|---|---|---|---|
| Execution accuracy | North-star | % of questions where executed query result matches the gold/verified result | **15/15 (100%), real measured** — full Router→Query Writer→Verifier pipeline against golden_set_v1.json's 15 executable questions (Sprint 2, `src/eval/eval_query_writer.py`), Claude Haiku 4.5, schema-grounded prompt. **Caveat: thin sample.** 15 questions is well short of the ~150-200 target for the locked golden set (`evaluation_plan.md` §2, Stage 5) — treat 100% as an early positive signal, not a durable claim; expect this to drop as the set grows to include harder/rarer cases. Two real bugs were found and fixed getting here (a Verifier false-positive on EXTRACT() date keywords, a Query Writer gap in DuckDB's date-arithmetic dialect) — see `docs/stage4_risk/risk_register.md` addendum. | ≥90% on golden set |
| Insight faithfulness | Supporting | % of explanations where the natural-language answer is fully supported by the query's actual result (RAGAS faithfulness) | **No baseline system exists to measure yet; treat as 0 until Sprint 2** -- unlike execution accuracy, there's no published reference point for faithfulness on our specific schema, so we don't project one; first real number comes from the Sprint 2 core-path RAGAS run | >=0.9 RAGAS faithfulness score |
| Ambiguity-handling floor | Guardrail (safety) | % of intentionally ambiguous questions (from adversarial synthetic set) that trigger a clarification instead of a guess | 0% (no system exists yet -- a naive single-LLM path has no clarification mechanism at all, so 0% is both the honest baseline and the reason this metric is a hard floor, not a dial) | >=85%, never regresses on any change |
| Latency at scale | Guardrail (perf) | p95 time from question to answer, at current data volume (99k orders, 112k items), under a stated concurrent-load condition | **Real measured, single-request (Sprint 2, `src/eval/eval_pipeline.py`): p50 6.58s, p95 13.56s.** ⚠️ **This is NOT the guardrail condition** — measured with zero concurrency, no queuing, no rate-limit contention. Two questions (gs004, gs011) already hit 11.7s/13.6s single-request, close to or past the 8s/15s targets before any concurrent load is added. This is an early warning, not a passing result: under the actual 20-concurrent-request condition (Stage 6/7), latency will likely be worse, not better, and the current no-gateway/no-caching setup (see architecture.md §4 gap, still open) has no mechanism to prevent that. Concurrent load testing is the real test; treat this number as "already tight," not "on track." | p95 ≤ 8s for lookup/aggregation, ≤15s for multi-hop comparative, **at 20 concurrent requests** (see NFR note below) |
| Cost per answered question | Guardrail (cost) | $ per successfully answered question in production inference, averaged over golden set run — **excludes one-time/offline synthetic-data-generation and DSPy-optimization spend**, which is tracked separately as development cost, not a per-question production cost | **Real measured (Sprint 2, `src/eval/eval_pipeline.py`): $0.00252 average across 18 questions, $0.04536 total run cost.** Comfortably under the $0.02 cheap-path ceiling. **Caveat: this is entirely cheap-path cost** — Narrator is still running on Haiku 4.5, not the Sonnet 5 default specced in architecture.md §5 (documented temporary simplification, see narrator.py). The escalated-path number (~$0.04 projected) is still unmeasured, since no question in this run triggered the Query Writer's Sonnet-escalation path either. | ≤ $0.02/question on cheap-path, ≤ $0.08 on escalated path |

This PRD carries **one north-star metric, one supporting metric, and three guardrail
metrics** (safety floor, latency ceiling, cost ceiling) -- matching the brief's requirement
of at least two guardrails (p.4). Guardrails must never be crossed even if execution
accuracy improves -- e.g. we will not accept a routing change that raises accuracy 2
points but drops ambiguity-handling below 85%, or doubles cost per question, without an
explicit tradeoff decision logged in the risk register. Ambiguity handling sits in
guardrails rather than supporting metrics because it is a strict safety floor, not a
quality dial we're trying to optimize upward opportunistically -- the brief's own framing
of "never guess" (p.5, wrong-query risk) makes it a floor, not a target to trade off.

## 7. Non-functional requirements

- **Latency budget**: p95 targets in section 6, measured **under a burst-load condition of 20
  concurrent requests** (matches the "handle bursty load" build requirement, Stage 6,
  p.7) -- not a single-request best case. Concurrency level is a v1 assumption based on
  Northstar's described backlog volume, not a client-confirmed number; revisit once real
  ticket-volume data is available (see Stage 1 open question).
- **Cost ceiling**: applies to **production, per-question inference cost only** --
  model calls made at answer time (planning, query-writing, verification, explanation).
  It explicitly **excludes** one-time or periodic offline costs: synthetic-data
  generation runs, DSPy prompt-optimization runs, and evaluation/judge-calibration runs.
  Those are tracked as a separate **development/eval cost line** in the token-economics
  report (Stage 7), so we don't distort the per-question unit economics that Jordan (Head
  of Analytics Ops) actually needs to defend the system's ongoing run cost. Enforced via a
  hard budget alarm on the production path (Stage 4/7).
  *Feasibility check (July 2026 pricing, current model generation)*: cheap path on
  Gemini 2.5 Flash-Lite ($0.10/$0.40 per MTok) lands near $0.003/question for a 2-3 hop
  agent path -- comfortable headroom under the $0.02 ceiling. Escalated path (clarify to
  re-plan to verify/narrate, mixing Claude Haiku 4.5 and Sonnet 5) lands near $0.04 --
  realistic but tight against the $0.08 ceiling, which is why semantic caching and
  cheap-first routing are load-bearing, not optional (Stage 6/7). Full model-routing
  decision table is a Stage 3 deliverable; this is a feasibility check only, not the
  final routing policy.
- **Confidence signal (operational definition)**: escalation to Devon's team (section 5
  assumption) is triggered by a **structural, not self-reported, confidence signal** --
  specifically, a deterministic pass/fail from the SQL-parser/schema-validation step
  (does the query reference real tables/columns, does it parse) combined with the
  result-verification agent's pass/fail against sanity checks (row-count bounds, null
  handling, join-grain check per section 3 findings). We do not rely on an LLM's self-reported
  confidence score, since that number is not grounded in anything verifiable. The
  empirical threshold for *how many* of these checks must pass is still set in Stage 7
  (section 9 open item), but the signal itself is structural by design, not a model guess.
- **Context window boundary**: with 73 product categories and a long-tail category
  distribution (section 3), naively appending the full schema/DDL and category catalog to every
  prompt would bloat input tokens and threaten the cost guardrail above. The system must
  retrieve only the schema slice and categorical values relevant to a given question
  (via the vector store -- Chroma, per the recommended toolbox, p.12) rather than
  including the entire catalog on every call. This is a hard constraint carried into the
  retrieval-layer design in Stage 3/6, not a nice-to-have.
- **Safety bar**: zero tolerance for write/destructive queries; zero tolerance for
  fabricated column/table names (must ground against actual schema or refuse).

## 8. Competitive teardown (completed here, informs scope above)

Two categories of existing product were reviewed for behavior on (a) an ambiguous
question and (b) a wrong-result scenario:

- **Pattern worth borrowing**: BI copilots that show the generated query inline and let
  the user expand/collapse it build trust faster than ones that hide it -- we adopt query
  exposure as a hard requirement (already in scope above), not an optional nicety.
- **Anti-pattern to avoid**: text-to-SQL tools that answer an ambiguous question by
  silently picking the most common interpretation and stating the number with full
  confidence, with no signal to the user that a judgment call was made. This is the
  exact failure mode the brief centers on ("a wrong query returns a confident, wrong
  number") and is why ambiguity handling is a named supporting metric, not an
  afterthought.

## 9. Open items for Stage 3 (Design)

- Confidence threshold for auto-escalation to human path
- Exact routing policy (which question categories go to cheap vs. strong model tier)
- Whether "delivered-only" is the default filter for status-sensitive questions, or
  whether the agent must always state its status assumption explicitly (leaning toward
  the latter, given the null-rate findings above)
