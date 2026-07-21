# Risk Register v1
Stage 4 - Assess and Mitigate Risk - Sprints 0-1, then maintained
Owner: shared (see per-risk owner below, per team charter working agreement)

Each top risk is tied to a specific design decision already made, not a future
intention -- per the brief's requirement (p.5). Likelihood/impact are qualitative
(High/Med/Low) at this stage since we have no production traffic yet; these get
replaced with measured rates once the golden-set evaluation (Stage 7) runs.

**Owner column meaning**: who is accountable for the mitigation staying correct over
time -- which is usually, but not always, the person who designed it. Where the two
differ, both are named.

| # | Risk | Likelihood | Impact | Owner | Mitigation (tied to design) | Residual risk |
|---|---|---|---|---|---|---|
| 1 | **Wrong query, confident answer** -- a query executes successfully but answers the wrong question, and the Narrator states it with full confidence | High (this is the central failure mode the whole brief is about) | High -- directly damages user trust (Priya persona) and can drive a wrong business decision | Vishal | Result Verifier agent is a mandatory hard gate before any answer reaches the Narrator (architecture.md section 1); Narrator receives only verified display_sql+result_summary, never raw model output; query is always exposed | **Medium.** Verification catches structural errors (join-grain, null-handling, schema-grounding) but not every semantic misread of intent -- this is why ambiguity handling exists as a separate guardrail (risk #2), not a substitute |
| 2 | **Ambiguous question misread** -- the system silently picks one interpretation of a genuinely ambiguous question and answers as if it were the only one | Med-High (~7% of volume estimated, Stage 1) | High -- this is the anti-pattern explicitly identified in our competitive teardown (PRD section 8) | Shanmuk (designed the Router/Clarifier split) / Ankit (accountable for the PRD guardrail it implements -- Product lens) | Router intercepts ambiguous questions before they reach Query Writer at all, routing to Clarifier (orchestration_decision_record.md); Ambiguity-handling floor is a hard guardrail metric, not optimized opportunistically (PRD section 6) | **Low-Medium.** Depends on Router's classification accuracy -- a question misclassified as unambiguous bypasses this mitigation entirely; golden set (eval plan) must include borderline cases to measure this specifically |
| 3 | **Unsafe or expensive query** -- a generated query is slow, resource-heavy, or (if a bug ever allowed it) destructive | Low (write access never exposed) / Med (expensive query) | High if destructive; Med if just slow | Vishal | Sandbox connection is read-only and pre-bound (never agent-constructed); tool contract explicitly forbids write access (agent_contract_result_verifier.md); timeout + row-return cap + cartesian-join rejection specified in architecture.md section 8 | **Low.** Read-only enforcement is structural (DB-level permissions), not just prompted -- the main residual risk is a slow-but-valid query blowing the latency guardrail, handled by the timeout, not a data-safety issue |
| 4 | **Hallucinated schema or metric** -- the system invents a column, table, or business-term definition that doesn't exist | Med | High -- silently corrupts every downstream step | Anvay | Query Writer must cite schema_lookup_refs for every identifier used (agent_contracts.json); an ungrounded identifier is an automatic Verifier fail (schema_grounded check), not a warning | **Low.** Contract-enforced, but only as strong as the Chroma retrieval layer's coverage -- a schema change not reflected in the vector store reintroduces this risk (ties to agent registry versioning, architecture.md section 6) |
| 5 | **Scale and cost blowup** -- many agent hops x many concurrent questions exceeds the cost guardrail | Med | Med (budget) but High if it forces an emergency model downgrade under load | Anvay | Model-routing policy reserves paid/strong tiers for only 2 of 6 agent steps (architecture.md section 5); semantic caching and cheap-first routing named as load-bearing, not optional (PRD section 7 footnote); hard budget alarm on the production path | **Medium.** The feasibility check (PRD section 7) is a projection, not a measured number yet -- real residual risk here is that measured cost under the Stage 6 burst-load test (20 concurrent requests) comes in above projection, which is exactly what that test exists to catch |
| 6 | **Join-grain overcounting** (Olist-specific instance of #1) -- naive COUNT(order_id) on an orders-items join overcounts, since 9.9% of orders have >1 item (Stage 2 finding) | High if unmitigated, Low as designed | Med -- wrong number, but a specific, catchable pattern | Vishal | join_grain_correct and no_orphaned_join are explicit Verifier checks (agent_contracts.json); this exact case is a canonical adversarial test in the Stage 5 synthetic eval set | Low, contingent on the adversarial set actually covering this case in Stage 5 |
| 7 | **customer_id vs. customer_unique_id confusion** (Olist-specific instance of #1) -- 99,441 distinct customer_id but only 96,096 customer_unique_id (Stage 2 finding); wrong key silently changes the answer to "how many customers" | High if unmitigated, Low as designed | Med | Vishal | Second canonical adversarial test case (PRD section 3); semantic-layer lookup should define "unique customer" once, centrally, rather than leaving it to per-query judgment | Low, same caveat as #6 -- depends on Stage 5 coverage, and on the semantic layer definition actually being built (currently a design intention, not yet built -- flagged honestly) |
| 8 | **Sandbox internals leak through the "exposed query" feature** -- the query-exposure requirement (a trust feature) becomes a trust *liability* if it leaks internal paths/aliases | Med (identified during Stage 3 design, not hypothetical) | Med -- reputational/security, not a wrong-answer risk, but erodes the same trust the feature is meant to build | Vishal | execution_sql/display_sql separation via AST reconstruction against an identifier allowlist, not string redaction (agent_contract_result_verifier.md) | Low, contingent on the allowlist mapping table being correctly maintained -- flagged in that doc as needing an owner when schema changes (open item, tied to agent registry, still unresolved) |
| 9 | **Individual viva failure** -- a team member can't defend a part of the system they didn't personally build | Med (process risk, not a system risk) | High -- the viva is an individual gate; the team's dimension score doesn't transfer (brief p.11) | Vishal (engagement lead -- this is a cross-cutting process risk, owned independently of the lens rotation below, not tied to whichever lens Vishal drives this sprint) | Team charter's cross-review working agreement (primary/secondary ownership, PR review outside one's own lens, weekly retro closing "generated but not understood" gaps) | Medium -- this is the least structurally-enforced mitigation in the register; it depends on the team actually doing the retros, not on anything the system itself enforces |

## Kill switch and graceful fallback (explicit, per brief p.5)

**Kill switch trigger conditions**: (a) Result Verifier confidence signal fails on 2
consecutive attempts for a single question (the retry-once cap defined in
architecture.md), (b) the cost guardrail is breached for 3 consecutive questions
(signals a systemic routing failure, not a one-off), or (c) the gateway's fallback chain
is exhausted (all configured models unavailable).

**Graceful fallback**: in every trigger case, the system does not retry indefinitely or
guess -- it hands off to Devon's team's escalation queue with the partial trace attached
(question, category, what was attempted, why it failed), so the human path starts with
context rather than from zero. This is the same "degrade to human, don't guess" principle
that governs the Clarifier's ambiguous-question handling -- it's one consistent policy
applied at two different trigger points, not two separate mechanisms.

## What's still open (carried forward, not hidden)

- Risks #6-#8's residual-risk claims depend on Stage 5 (synthetic data) and the semantic
  layer actually being built as designed -- this register describes the *intended*
  mitigation state, and Stage 5/6 need to confirm it's real, not assumed.
- Risk #9 is the weakest mitigation in this register precisely because it's a team
  behavior, not a system control -- worth the team's own attention, not something I can
  design around from here.
- **This register reflects Stage 2/3 knowledge only.** It has not yet been through the
  team charter's own Sprint 1 checkpoint ("architecture review -- other three challenge
  it"), and doesn't yet cover risks that can only surface once Stage 5 (synthetic-data
  quality/bias), Stage 6 (concurrency and observability under real load), or Stage 8
  (deployment/rollback specifics beyond the kill switch above) actually happen. "v1" here
  means done for where the project currently is, not final -- the brief's own cadence
  ("Sprints 0 to 1, then maintained") expects this to keep changing.

## Addendum (Sprint 2): ground truth needs verification too

Risk #1 ("wrong query, confident answer") assumed the failure mode lives in the
*agent's* output. Live Query Writer testing surfaced a case where it was the golden
set's own hand-written gold SQL that was wrong: gs007's original query joined
order_items unnecessarily, silently excluding 775 real orders (603 unavailable +
164 canceled, verified against the sandbox) that were genuinely placed but never got
a line-item row. The Query Writer's simpler, join-free answer was actually more
correct than the "gold" answer it was being graded against.

**Implication for this risk register**: mitigation #1 (mandatory Verifier gate) checks
whether a query is internally correct - schema-grounded, correct join grain, sane row
count - but it cannot catch a case where the reference answer itself encodes the wrong
business logic. That's a distinct failure mode, worth its own line:

| # | Risk | Likelihood | Impact | Owner | Mitigation | Residual risk |
|---|---|---|---|---|---|---|
| 10 | **Golden-set/gold-SQL error** -- a hand-written reference answer used to grade the system is itself semantically wrong, silently lowering measured accuracy or masking a real bug | Med (found once already, in a set of just 18 questions) | Med -- corrupts the accuracy metric itself, not just one answer; risks both false "system is wrong" and false "system is right" conclusions | Anvay (Data & Eval lens) | Cross-check any golden-set item flagged as a live-agent mismatch against real data before assuming the agent is wrong (as done here) -- a mismatch is a signal to investigate, not an automatic fail | Medium -- this check is currently manual/reactive (triggered by noticing a suspicious mismatch), not systematic; a golden set audit pass before Stage 5/6 lock would lower this |

Fixed: gs007's gold_sql corrected; gs018 added as the real join-grain adversarial
test (the original question could be answered correctly without ever joining
order_items, so it stopped testing what it was designed to test).

## Addendum (Sprint 2): latency guardrail is already tight, pre-concurrency

Full pipeline evaluation (src/eval/eval_pipeline.py, 18 questions, single-request,
zero concurrency) measured p50 6.58s, p95 13.56s. Two individual questions (gs004,
gs011) hit 11.7s and 13.6s on their own - close to or past the 8s/15s targets before
any concurrent load is added. This matters because the guardrail is specifically
defined UNDER 20 concurrent requests (PRD section 6/7), and nothing in the current
build (no LLM gateway, no caching, no queuing - see architecture.md section 4 open
gap) would make concurrent latency better than single-request latency. It will
plausibly be worse.

| # | Risk | Likelihood | Impact | Owner | Mitigation | Residual risk |
|---|---|---|---|---|---|---|
| 11 | **Latency guardrail breach under concurrent load** -- single-request latency is already near the guardrail ceiling; the system has no gateway, caching, or queuing mechanism yet to prevent concurrent load from pushing it over | High (measured single-request numbers already close to target; nothing currently mitigates concurrency) | Med -- breaches a named guardrail (PRD section 6), which per that document's own rule "must never be crossed" without an explicit logged tradeoff | Vishal (Build & Scale lens) | None implemented yet. Candidate mitigations, all still open: (a) build the LLM gateway with connection pooling/queuing (architecture.md section 4, currently undone), (b) semantic caching for repeated/similar questions (architecture.md, Stage 6/7), (c) reduce agent hop count on the hot path, (d) parallelize independent steps where possible | High until Stage 6/7 concurrent load testing actually runs and a mitigation is chosen and implemented - this is not yet mitigated at all, only measured |

This is flagged now, in Sprint 2, rather than waiting for the formal Stage 6/7 load
test, because the single-request signal is already concerning enough that Sprint 3
("Harden, Scale, Optimize" per the brief's cadence) should treat this as a known
priority going in, not a fresh discovery.
