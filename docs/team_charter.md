# Team Charter

## Squad
- **Vishal** 
- **Shanmuk**
- **Anvay**
- **Ankit**

## Why this matters now
The brief scores five dimensions at the team level, then applies an **individual viva
gate** — each person must be able to defend *any* part of the system, not just their own
slice (p.11: "walk through code you did not personally write, justify a design
tradeoff... explain a token-economics decision"). So role split organizes *who drives*
each area, but it is not a license for anyone to only understand their own piece.

## Ownership by lens (rotate review, not just build)

**Corrected from the original draft** — each person now drives exactly one lens:

| Lens | Primary driver | Secondary (reviews + must-defend) |
|---|---|---|
| Product (personas, PRD, metrics, discovery) | **Ankit** | Shanmuk |
| Solution architecture (topology, orchestration, gateway, registry) | Shanmuk | Anvay |
| Engineering — build & scale (agents, concurrency, caching, observability) | **Vishal** | Ankit |
| Engineering — data & eval (synthetic pipeline, RAGAS, DSPy, golden set, judge calibration) | **Anvay** | Vishal |

Secondary reviewers are unchanged from the original draft — only who *drives* each lens
rotated (Product: Vishal → Ankit; Build & Scale: Anvay → Vishal; Data & Eval: Ankit →
Anvay). Solution architecture is untouched: Shanmuk still drives it, Anvay still reviews
it — note Anvay now also *drives* a different lens (Data & Eval) while still reviewing
this one, which is fine under the working agreement below, just worth being aware of
when scheduling review time.

Every document produced so far under the old split (PRD, evaluation plan, Result
Verifier contract, risk register owners) has been updated to match this table — see each
file's own "Owner:" line.

Risk register, ops runbook, and Demo Day materials are shared — every person adds and
signs off on at least one risk and one section of the runbook, since these are exactly
the artifacts a viva examiner probes for individual understanding.

## Sprint cadence (mapped to the 8-stage lifecycle)

| Sprint | Stages | All-hands checkpoint |
|---|---|---|
| 0 | Discover, Define | PRD v1 review — everyone signs off before Sprint 1 |
| 1 | Design, Risk (start) | Architecture review — each driver presents their lens, other three challenge it |
| 2 | Data, Build (core) | Working core path demo + cost baseline |
| 3 | Build (harden), Verify (deepen) | A/B + DSPy results review, regression suite green |
| 4 | Verify, Operate | Dry-run of the 20-min presentation + viva prep — cross-quiz each other on the other lenses |

## Working agreement
- One shared repo, one shared risk register, one shared metrics doc — no forked truth.
- Each PR gets reviewed by someone outside that lens, not just the primary driver's
  secondary — this is what makes the viva survivable.
- Weekly retro logs what was generated but not yet understood by the non-drivers, and
  closes that gap before the next sprint starts.
