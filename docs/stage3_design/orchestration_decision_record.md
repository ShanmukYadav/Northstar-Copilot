# Orchestration Decision Record
Stage 3 - Design - v1
Owner: Shanmuk (drives) - Reviewer: Anvay

## The four patterns on the table

| Pattern | What it's good at | Where it breaks down for us |
|---|---|---|
| **Router** | Cheap, fast dispatch to the right specialist path | Alone, it can't handle a question that needs decomposition (comparative/multi-hop) -- it can classify but not plan |
| **Plan-and-execute** | Decomposing genuinely multi-step questions, replanning on failure | Overkill and slow for the 65% of volume (section 3 PRD) that's simple lookup/aggregation -- pays a planning-latency tax on every question |
| **Sequential stages** | Predictable, easy to trace, easy to verify at each hand-off -- matches our "never guess, always verify" mandate directly | Rigid: forces every question through every stage even when a stage is a no-op, and doesn't naturally handle "this needs decomposition" without bolting something else on |
| **Network of specialists** | Clean single-responsibility agents, swappable, matches our agent-contract requirement | Without *some* control structure, a flat network needs its own routing logic anyway -- it's not actually an alternative to the other three, it's how the other three are implemented |

## Decision: Router to Sequential specialist chain, with Plan-and-Execute as a sub-path

We adopt a **hybrid**, not a single pure pattern, because the four options aren't
mutually exclusive -- "network of specialists" describes *what* the agents are, and
Router/Sequential/Plan-and-execute describe *how control flows between them*.

**Concretely:**

1. A **Router** agent classifies every incoming question against the Stage 1/2 taxonomy
   (simple lookup, aggregation, trend, comparative, ambiguous, out-of-scope) and produces
   a routing decision plus a category confidence.
2. **Simple lookup, aggregation, trend** questions (approx 80% of volume, PRD section 3) go down a
   **fixed sequential chain**: Query Writer -> Result Verifier -> Narrator. Sequential
   because each stage's output is a hard precondition for the next (you cannot verify a
   query that wasn't written, you cannot narrate a result that wasn't verified) -- this
   is exactly the "interpret -> write -> execute -> verify -> explain" flow the brief
   describes (p.4), and it's the cheapest, most traceable path for the bulk of volume.
3. **Comparative/multi-hop** questions (approx 10% of volume) go down the same chain but with
   a **Planner** agent inserted before Query Writer, turning it into a
   **plan-and-execute** sub-path: Planner decomposes into steps -> Query Writer executes
   per step -> Result Verifier checks each step and the combined result -> Narrator
   explains. We don't pay this planning cost on the 80% that doesn't need it.
4. **Ambiguous** questions (approx 7% of volume) are intercepted by the Router before reaching
   Query Writer at all, and routed to a **Clarifier** agent that asks the user a specific
   question instead of guessing -- this is the direct implementation of the
   ambiguity-handling guardrail (PRD section 6).
5. **Out-of-scope/destructive** questions (<3%) are refused by the Router directly -- no
   downstream agent ever sees them, since no agent in the system holds
   write/destructive tool access anyway (defense in depth, matches the Result Verifier
   contract's tools_forbidden list).

## What we explicitly reject and why

- **Pure plan-and-execute for everything**: rejected -- adds latency and cost to simple
  lookups for no accuracy benefit, and works against the cost guardrail (PRD section 6/7).
- **Pure router-and-dispatch with monolithic per-path agents** (one big agent per
  category instead of composed specialists): rejected -- fails the brief's requirement
  that agent contracts be swappable schemas (p.4); a monolithic agent can't be swapped
  without rewriting the whole path, and can't be independently verified at each hop,
  which undermines the "never guess, always verify" design principle this whole system
  is built around.
- **Multi-agent debate / mixture-of-agents** for the core path: rejected for v1 as a
  frontier technique that doesn't clear its cost -- it multiplies calls (and cost/latency)
  for a system whose failure mode (join-grain errors, status-filter ambiguity) is better
  caught by deterministic verification than by having two LLMs argue. Logged as a
  "raising the ceiling" candidate for Stage 7 A/B testing on the hardest adversarial
  slice only, not the default path.

## Control-flow summary
question
|
v
[Router] --refuses--> out-of-scope response (no downstream agent invoked)
|
|--ambiguous--> [Clarifier] --> (user reply) --> back to Router with resolved question
|
|--simple/agg/trend--> [Query Writer] -> [Result Verifier] -> [Narrator] -> answer
|
+--comparative/multi-hop--> [Planner] -> [Query Writer] x N -> [Result Verifier] -> [Narrator] -> answer
Result Verifier failure (any path) --> escalation to human queue (Devon's team),
per the structural confidence_signal defined in the Result Verifier contract.

---

## Addendum (Sprint 2): Router category simplification, based on empirical evaluation

**What happened**: once a live Router agent was built and run against the 17-question
golden set, raw category accuracy was 12/17 (71%). All 5 misses were the same pattern:
the Router labeled a plain single-filter COUNT question (e.g. "how many unique
customers do we have?") as simple_lookup, while the golden set had labeled the same
question aggregation.

**Root cause**: this was not a Router defect. The Router was applying its own
system-prompt definition of "aggregation" correctly and consistently (requires GROUP BY
/ ranking / averaging across a dimension); the golden set's labels were assigned from
Stage 1's looser taxonomy, which called any question using an aggregate function
(COUNT/AVG) "aggregation" even without grouping. The two definitions disagreed with
each other, not with reality.

**Why it doesn't matter operationally**: per this document's own control-flow decision
above, simple_lookup, aggregation, and trend all route to the identical downstream
chain (Planner passthrough to Query Writer to Verifier to Narrator). Recomputing
accuracy against functional routing group instead of raw label gave **17/17 (100%)** --
every question reached the correct downstream path, including all 5 "misses."

**Decision**: collapse simple_lookup / aggregation / trend into a single Router
category, standard_query, since carrying three labels the system doesn't act on
differently only adds classification-boundary failure surface for no benefit. The
finer distinction (is this really an aggregation, does it need date bucketing) still
exists downstream -- it lives in the Query Writer's assumptions_stated field
(agent_contracts.json) rather than in the Router's job. Golden-set and synthetic-set
labels (simple_lookup, aggregation, trend, rare_schema_corner, etc.) are **unchanged**
-- those track test-coverage breadth, which is still useful at that finer grain, even
though the Router itself no longer needs to reproduce it.

**Updated category set**: standard_query, comparative, ambiguous, out_of_scope.
Reflected in agent_contracts.json and architecture.md; not reflected in
golden_set_v1.json or synthetic_v1.json by design (see above).
