# Design Spec - Northstar Insight Copilot
Stage 3 - Design - v1
Owner: Shanmuk (drives) - Reviewer: Anvay

This is the spec a new engineer should be able to build from without asking us
questions. It assumes the PRD (`docs/prd.md`) as ground truth for scope and metrics.
The orchestration reasoning (why Router to Sequential + conditional Plan-and-Execute,
and what we rejected) lives in `docs/stage3_design/orchestration_decision_record.md` --
this doc picks up from that decision and specifies the resulting system.

**One reconciliation note**: this spec adds a **retry-once** rule that the decision
record doesn't call out explicitly -- if the Verifier fails, the system retries the
Query Writer step exactly once with the failure reason as added context, before
escalating to Devon's team. This bounds the retry to prevent an infinite/expensive
loop, and directly protects the cost and latency guardrails (PRD section 6).

---

## 1. System architecture diagram

```mermaid
flowchart TD
    U[User question] --> GW[LLM Gateway<br/>LiteLLM]
    GW --> RTR[Router / Classifier Agent<br/>cheap tier]

    RTR -->|out_of_scope or destructive| REFUSE[Hard refuse<br/>+ reason shown]
    RTR -->|ambiguous| CLAR[Clarifier Agent<br/>cheap tier]
    CLAR -->|user answers| RTR
    CLAR -->|still unclear after 1 round| ESCALATE[Escalate to human<br/>Devon's queue]

RTR -->|simple_lookup / aggregation / trend| PLN1 → RTR -->|standard_query| PLN1    RTR -->|comparative| PLN2[Planner: multi-step<br/>strong tier]

    PLN1 --> QW[Query Writer Agent]
    PLN2 --> QW

    QW <-->|lookup| SCHEMA[(Schema + Semantic<br/>Layer Lookup tool<br/>Chroma vector store)]
    QW --> SANDBOX[[SQL Execution Sandbox<br/>read-only, pre-bound connection,<br/>timeout, cost guard]]

    SANDBOX --> VER[Verifier Agent<br/>produces execution_sql internally,<br/>emits display_sql only]
    VER -->|fails, retry budget remaining| RETRY{Retry once with<br/>failure reason}
    RETRY -->|yes, 1 attempt used| QW
    RETRY -->|already retried| ESCALATE

    VER -->|passes| NAR[Narrator Agent<br/>strong tier by default<br/>receives display_sql only]
    NAR --> CHART[Charting tool<br/>optional]
    NAR --> ANS[Answer + display_sql<br/>+ confidence + chart]
    ANS --> U

    subgraph Cross-cutting
        REG[Agent Registry]
        OBS[Observability: traces,<br/>logs, cost meter]
        MEM[Memory / State store]
    end

    GW -.-> REG
    GW -.-> OBS
    RTR -.-> MEM
    CLAR -.-> MEM
```

**Path through the system**: every question enters through the gateway, gets classified
by the Router, and either gets refused (destructive intent), clarified (ambiguous), or
proceeds through Planner to Query Writer to Sandbox to Verifier to Narrator. Control passes
between agents only at these named handoffs -- no agent calls another agent directly,
which is what keeps the topology swappable (section 3-4) and traceable (Stage 6/7). Note the
Narrator never receives execution_sql -- only the Verifier's sanitized display_sql --
so a leak would require a bug in the Verifier's AST reconstruction, not a missed
downstream redaction step.

---

## 2. Agent topology

| Agent | Single responsibility | Input | Output | Tools it may call | Model tier |
|---|---|---|---|---|---|
|**Classify question into simple_lookup **/ aggregation / trend / comparative / ambiguous / out_of_scope → Classify question into standard_query / comparative / ambiguous / out_of_scope (collapsed from 6 categories in Sprint 2 - see orchestration_decision_record.md addendum)|
| **Clarifier** | Turn an ambiguous question into either a clarifying question back to the user or an explicitly stated assumption | NL question + ambiguity reason | Clarifying question, OR question + stated assumption | Memory (state store) | Cheap (Gemini 2.5 Flash-Lite in production; free open model in dev) |
| **Planner** | Decompose into 1 query (passthrough) or 2+ queries + merge step (comparative only) | Category + NL question | Ordered step list, each step = one query intent | Schema lookup | Cheap for passthrough, Mid (escalates to Strong on failure) for comparative |
| **Query Writer** | Produce SQL for one step, grounded strictly in real schema | Step (query intent) + schema context | SQL text + tables/columns referenced | Schema + semantic layer lookup | Mid default (Claude Haiku 4.5), escalates to Strong (Sonnet 5) only if verification fails -- see section 5 |
| **Verifier** | Sanity-check the executed result before it reaches the user | SQL + result set + question | pass/fail + reason + confidence score | Result-verification tool | Deterministic rules first (no model call); Cheap (Flash-Lite) only for judgment-call checks |
| **Narrator** | Turn a verified result into a plain-language answer that only states what the query actually computed | Verified result + SQL + question | NL answer + exposed SQL + confidence label | Charting tool (optional) | **Strong (Claude Sonnet 5) by default** -- insight faithfulness is a named PRD metric, so narration quality is worth the tier; may downgrade to Mid (Haiku) if Stage 7 eval shows no faithfulness loss, see section 5 |

Every agent is single-purpose by design -- this is what lets any one agent be swapped
(e.g. a stronger Query Writer model) without touching the others, and it's what makes
"explain any agent" survivable at the individual viva: each one is a one-sentence job.

---

## 3. Agent contracts

All agent I/O is JSON, validated against a schema before it's allowed to move to the
next stage. Full schemas live in `docs/stage3_design/agent_contracts.json`. Shape:

```json
{
  "router_output": {
    "category": ""simple_lookup | aggregation | trend | comparative | ambiguous | out_of_scope "→ "standard_query | comparative | ambiguous | out_of_scope"",
    "confidence": "float 0-1",
    "reason": "string, 1 sentence"
  },
  "query_writer_output": {
    "sql": "string, read-only SELECT only",
    "tables_used": ["string"],
    "columns_used": ["string"],
    "assumptions_stated": ["string"]
  },
  "verifier_output": {
    "status": "pass | fail | needs_retry",
    "checks_run": ["row_count_sane", "null_handling_declared", "join_grain_correct", "schema_grounded"],
    "confidence": "float 0-1",
    "failure_reason": "string | null"
  }
}
```

A malformed output at any stage is treated as a verifier:fail and routes to retry-once
to escalate, never silently passed forward. This is the concrete implementation of the
PRD's "never invent a number" requirement.

---

## 4. LLM gateway

Single point every model call passes through (LiteLLM). Responsibilities:
- Holds provider keys (never in agent code).
- Enforces the routing policy (section 6) -- agents request a *task type*, not a model name.
- Timeout: 10s per call (aligned to PRD latency guardrail), with one retry on timeout.
- Fallback chain: primary free-tier model to secondary free-tier model to paid fallback,
  logged every time a fallback fires (feeds the cost/reliability dashboard, Stage 6/7).
- Rate-limit handling: exponential backoff, capped at 2 retries before escalating to the
  human path rather than hanging the user.

## 5. Model-routing policy

Dev/iteration uses free-tier open models throughout (per the brief's "free-first"
guidance, p.12); the table below is the **production routing policy**, which is what
the PRD's cost guardrail is actually measured against.

| Task | Default model | Fallback chain | Why |
|---|---|---|---|
| Router/Classifier | Gemini 2.5 Flash-Lite ($0.10/$0.40 per MTok) | Open free-tier model (DeepSeek/Qwen via LiteLLM) to hard fail to human queue | High volume, low reasoning depth -- cheapest tier clears this easily |
| Clarifier | Gemini 2.5 Flash-Lite | Same as Router | Templated, low reasoning |
| Planner - passthrough | Gemini 2.5 Flash-Lite | Same as Router | Single-step, no real planning needed |
| Planner - comparative | Claude Haiku 4.5 ($1/$5) | Gemini 2.5 Flash-Lite (degraded quality, logged) | Multi-step decomposition needs more reasoning than Flash-Lite reliably gives |
| Query Writer | Claude Haiku 4.5 | Claude Sonnet 5 (only if Haiku output fails schema-grounding check) | SQL correctness is the accuracy bottleneck -- worth the tier; escalate only on verified failure, not preemptively |
| Verifier | Deterministic rules first (no LLM call); Gemini 2.5 Flash-Lite only for the judgment-call checks | -- | Rule-based checks are free and faster; LLM only where a check genuinely needs judgment |
| Narrator | Claude Sonnet 5 ($2/$10 intro pricing) | Claude Haiku 4.5 (if cost guardrail pressure requires) | Insight faithfulness is a named PRD metric -- narration quality is worth the tier on the escalated path; cheap path may downgrade to Haiku if golden-set eval shows no faithfulness loss |

This table is the enforcement mechanism for the PRD's cost-per-question guardrail: the
feasibility check (PRD section 7) assumed exactly this routing -- Flash-Lite for high-volume
low-reasoning steps, Haiku/Sonnet reserved for the two steps (Query Writer, Narrator)
where quality actually moves the north-star and supporting metrics. Escalating Query
Writer to Sonnet is failure-triggered, not default, to protect the cost ceiling.

## 6. Agent registry

Each agent is registered with: name, version, single-responsibility description, input/
output schema reference, allowed tools, model tier, and an owner (per the team charter).
Registry is a simple versioned JSON/YAML file at build time (Stage 6) -- no need for a
dynamic service given team size and scope; explicitly deferred as a "raising the
ceiling" item if we adopt MCP for tool portability later.

- **Discovery**: the orchestrator (LangGraph graph definition) loads the registry file
  at startup and resolves each graph node's agent by name+version lookup -- there is no
  runtime service-discovery step, since the topology is fixed at build time, not
  dynamically assembled per-request. This is a deliberate simplicity choice for v1: a
  fixed topology is easier to trace and verify (matches our "never guess" design
  principle) than a dynamically-discovered one, at the cost of needing a redeploy to
  change the graph shape -- an acceptable tradeoff at this scale.
- **Invocation**: an agent is never called directly by another agent's code -- every
  call goes through the gateway (section 4), which looks up the target agent's registered
  model tier and tool permissions before dispatching. This is what makes "swap Query
  Writer's model" a one-line registry change rather than a code change in the Planner or
  Verifier that call it.
- **Versioning**: a version bump on any agent's contract requires a corresponding update
  to `agent_contracts.json` and re-running the golden-set regression suite (Stage 7)
  before the new version can be marked active in the registry -- this is what prevents a
  silent contract drift from breaking a downstream agent that assumed the old shape.

## 7. Memory and state

- **Within one interaction**: the full agent trace (router decision to clarifier exchange
  to plan to SQL to result to verification to answer) is held in a request-scoped state
  object, passed explicitly between agents -- never implicit shared memory.
- **Across interactions**: only a clarification exchange persists briefly (so a follow-up
  answer to a clarifying question resolves back to the original question) -- capped at one
  round-trip per PRD scope (no multi-turn conversational memory in v1).
- Nothing about a user's question or data is persisted beyond what's needed for the
  observability trace (Stage 6/7) and the audit trail Jordan's persona needs.

## 8. Tool specifications

| Tool | Purpose | Constraints |
|---|---|---|
| **SQL execution sandbox** | Runs Query Writer's SQL against a read-only copy of the Olist data | SELECT-only (enforced at the sandbox layer, not just prompted), query timeout, row-return cap, cost/complexity guard (reject cartesian-join-shaped queries before execution) |
| **Schema + semantic-layer lookup** | Grounds Query Writer/Planner in real table/column names and business-term definitions (e.g. what "delivered" means, per Stage 2 findings) | Read-only metadata; Query Writer must cite which lookup result it used -- ungrounded column references are an automatic Verifier fail |
| **Result-verification tool** | Runs deterministic sanity checks: row count plausibility, null-handling was declared, join grain matches question intent, no orphaned joins | Rule-based first, LLM-judgment second -- rules alone catch the two canonical adversarial cases from Stage 2 (item-count overcounting, customer_id vs customer_unique_id) |
| **Charting tool** | Optional -- renders a chart spec for trend/comparative answers | Only invoked after Verifier passes; never generates a chart from unverified data |

## 9. Operational definitions (so later metrics are unambiguous)

- **"Correct" (execution accuracy)**: the executed query's result set matches the gold
  query's result set on the same data snapshot, including correct handling of the
  null/grain cases identified in Stage 2.
- **"Faithful" (insight faithfulness)**: every number in the Narrator's NL answer traces
  back to a value present in the verified result set -- nothing added, nothing rounded
  without saying so.
- **"Handled" (ambiguity handling)**: the system either asks a clarifying question or
  explicitly states its interpretation assumption in the answer -- silence on an ambiguous
  read counts as a failure, even if the guessed answer happens to be numerically right.

---

## Open items carried to Stage 4 (Risk)

- Exact confidence threshold at which Verifier triggers retry vs. escalate
- Whether Planner's comparative-path step count has a hard cap (cost guardrail)
- Kill-switch trigger conditions (formalized in the risk register)
