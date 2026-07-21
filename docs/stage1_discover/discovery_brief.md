# Stage 1 — Discover and Probe
Northstar Analytics - Autonomous Analytics and Insight Copilot

## 1. The work as it actually arrives

Northstar's analysts currently sit as a query bottleneck between business users and the
data warehouse. Requests arrive as Slack messages or ticket-queue items, almost always
in plain English, almost never as SQL. Before building anything, we need to know what
those requests actually look like -- not what we assume a "business question" looks like.

Since we don't have Northstar's live ticket log, Stage 1 works from two proxies until the
real backlog is available (see probing questions, section 4):

1. **The shape of the target schema itself** (Olist: 9 relational tables -- orders, order_items,
   order_payments, order_reviews, customers, sellers, products, geolocation, product
   category translation). The schema's join paths tell us what kinds of questions are even
   answerable, and where ambiguity will live (e.g. "delivery time" could mean
   order-to-delivery, purchase-to-carrier-handoff, or estimated-vs-actual delta).
2. **Published text-to-SQL benchmarks (Spider, BIRD)**, which encode a decade of observed
   question patterns from real analytics users: lookups, aggregations, multi-hop joins,
   nested/comparative questions, and -- critically for BIRD -- questions that require
   external knowledge or reasoning beyond the schema alone.

## 2. Question taxonomy (working hypothesis, to validate against real tickets)

| Category | Example (Olist-flavored) | Est. share of volume* | Why it matters |
|---|---|---|---|
| Simple lookup / filter | "How many orders shipped late in March 2018?" | ~35% | High volume, low risk, ideal for cheap-model routing |
| Aggregation / ranking | "Which product category has the highest average review score?" | ~30% | Needs correct GROUP BY + join grain; common source of silent errors |
| Trend / time-series | "How did monthly revenue change over 2017-2018?" | ~15% | Needs correct date bucketing; easy to get subtly wrong |
| Comparative / multi-entity | "Compare delivery delay between Sao Paulo and Rio sellers" | ~10% | Multi-join, higher ambiguity |
| Ambiguous / underspecified | "Why are sales down?" | ~7% | No single correct query exists -- this is where guessing causes harm |
| Out-of-scope / destructive intent | "Update the price of X" | <3% | Must be refused, not attempted -- read-only boundary |

*Percentages are a working hypothesis based on BIRD/Spider question-type distributions
and typical BI ticket queues, **not yet measured on Northstar's real data**. This gets
replaced with actual numbers in Stage 2 once the dataset is profiled (row counts, null
rates, category cardinality) and, ideally, once we have a real ticket sample.

## 3. Personas (draft -- finalized with Stage 2 job-to-be-done statements)

1. **Priya, Regional Ops Manager (primary user)** -- non-technical, asks 5-10 questions/week,
   trusts the tool completely, has no way to sanity-check a SQL query herself. Goal: fast
   answers she can act on. Frustration: has been burned before by a "confident but wrong"
   number from a different tool.
2. **Devon, Senior Data Analyst (escalation point)** -- technical, currently answers the
   backlog manually. Goal: get freed from repetitive lookups to work on real modeling.
   Frustration: doesn't trust automation with anything that could mislead a VP.
3. **Sam, Category Manager (power user)** -- semi-technical, asks comparative and trend
   questions, wants to drill into charts. Goal: self-serve without waiting in the queue.
   Frustration: existing BI dashboards don't cover ad hoc questions.
4. **Jordan, Head of Analytics Ops (accountable for cost/quality)** -- owns the budget and
   the "did this system embarrass us" question. Goal: predictable cost per question and an
   audit trail. Frustration: black-box AI tools with no way to verify an answer post hoc.

## 4. Probing questions we would put to the client

- **Volumes and peaks**: How many questions/week today? Any daily/monthly seasonality
  (e.g. month-end reporting spikes)?
- **Escalation boundary**: What must always route to a human analyst rather than be
  automated (e.g. anything touching finance/legal-sensitive numbers)?
- **Destructive actions**: Confirm the system is read-only -- no write/update capability,
  ever, regardless of how the question is phrased.
- **Freshness**: How current must data be? Can the copilot run against a snapshot, or
  does it need live warehouse access?
- **Definition ownership**: Who owns the canonical definition of ambiguous business terms
  ("active customer," "on-time delivery")? Is there an existing semantic layer/metrics
  dictionary, or do we need to define one?
- **Failure tolerance**: What's an acceptable wrong-answer rate before a user loses trust
  and reverts to the analyst queue?

Where we can't ask (no live client), we state and mark the assumption. Marked assumptions
so far: **read-only, no destructive actions, ambiguous questions must be clarified rather
than guessed, and Devon's team remains the escalation path for anything below a confidence
threshold.**

## 5. Competitive teardown (completed in Stage 2 PRD, see docs/prd.md section 8)

Target: two real analytics/text-to-SQL products (e.g. a BI copilot feature and a
general text-to-SQL tool). For each, observe behavior on (a) a deliberately ambiguous
question and (b) a question the tool answers wrong. Bring back one pattern worth
borrowing, one anti-pattern to avoid.

## 6. Prioritized map of the work (initial cut)

Ordered by (estimated volume x estimated automatability), pending real data:

1. Simple lookups/filters -- automate first, cheap-model path
2. Aggregation/ranking -- automate with mandatory result verification
3. Trend/time-series -- automate with date-bucketing checks
4. Comparative/multi-entity -- automate, route to stronger model tier
5. Ambiguous questions -- never guess; clarify-then-answer flow
6. Out-of-scope/destructive -- hard refuse, always

## 7. Open questions carried into Stage 2

- Exact volume split once real ticket data (or a reasonable proxy) is available
- Whether Olist's date range (2016-2018) is treated as "live" data or explicitly framed
  as historical in the product copy, to avoid user confusion
- Which ambiguous-term definitions need a semantic layer entry before Sprint 1
