# Contract-authority check — deterministic accept without JustTCG

**Status:** complete; no contract amendment drafted  
**Pin:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**Frozen parent:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0  
**Question:** Does D-032 auto-accept at score 1.00 with JustTCG disabled require a contract amendment?  
**Answer:** **No.** Frozen §5 and §13.1 already authorize it. The planning remark about an amendment applies only to auto-accept in the **ambiguous** band.

This file is a citation record. It does not amend the contract. Scoring
policy freeze, if applied, remains §16 detail. Implementation stays locked.

## Exact frozen clauses

### Resolution hierarchy

`CONTRACT.md` §1:

> Local matching -> JustTCG validation -> Human review -> Verified database write

`CONTRACT.md` §8: `external_validation_pending` is **optional**.

The hierarchy is the full pipeline. It does not require JustTCG on every intake. Optional external validation plus §13.1 skip lookup for unique high local matches.

### Automatic acceptance

`CONTRACT.md` §5 table, first row:

> Exact local match | `>= 0.95`, unique candidate, no conflicts | Accept identity locally

`CONTRACT.md` §5 additional auto-accept conditions:

> The highest-scoring candidate is unique.  
> The margin over the second candidate meets the configured minimum.  
> Game, set, and collector number do not conflict.  
> Printing, language, and edition are resolved when relevant.  
> No required identity field is inferred solely from price similarity.

`CONTRACT.md` §13.1:

> A unique `>= 0.95` local match is accepted without an external request.

This is the controlling specific rule. JustTCG is not required for that case.

### JustTCG fallback

`CONTRACT.md` §6 permitted triggers are **only**:

- local confidence in the **ambiguous** band;
- stable-id validation/enrichment;
- stale/missing **price** data;
- distinguishing multiple local candidates;
- refreshing condition/printing-specific **price**.

Exact unique local match is not a permitted JustTCG trigger. Calling JustTCG on a 1.00 unique match would be unnecessary spend, not a contract duty.

### Abstention when JustTCG is disabled

`CONTRACT.md` §6: ambiguous match → “Attempt JustTCG validation **if budget permits**.”

`CONTRACT.md` §15:

> Emergency disabling of external lookup or automatic acceptance is permitted as a safety action.

`CONTRACT.md` §6 outcome for timeout/exhausted credits/outage: keep pending; never auto-accept.

`CONTRACT.md` §3.10: provider failure never silently accepts an uncertain card.

`CONTRACT.md` §7: human review is mandatory for multiple printings, unresolved language/finish, missing required evidence, identifier conflicts.

Therefore: lookup off / budget 0 ⇒ ambiguous, weak, duplicate, missing, or conflicting cases **abstain or reject**. They do **not** auto-accept. D-032 matches this.

### Human review

`CONTRACT.md` §7 lists mandatory review cases. A unique exact local match that already satisfies §5 auto-accept is **not** in that list.

## Apparent conflict (planning vs D-032)

`PLAN-SLICE-01-INTAKE-ABSTENTION.md` §16:

> An amendment is required only if the owner later wants auto-accept in the **ambiguous band** without JustTCG, different thresholds, or agents auto-accepting.

That sentence is about **0.70–0.9499** auto-accept without lookup, which **would** need an amendment (§5 ambiguous row + §6).

D-032 does **not** do that. It auto-accepts only score **1.00**, six exact fields, one eligible identity, margin ≥ 0.10. That is a subset of §5 “exact local match” and §13.1. It is stricter than `>= 0.95`, not weaker.

Mutable decisions (D-032) and the scoring file cannot override the contract. They do not need to: the frozen text already allows this case.

## Compatibility with existing amendments

| Amendment | Frozen? | Effect on this case |
|---|---|---|
| 1.1.0 notifications | Proposed, not identity | Delivery must not change workflow outcomes. Irrelevant to local accept. |
| 1.1.1 / 1.1.2 | Frozen notification backend | Do not alter §5/§6/§13 identity rules. |

No clash. Do not freeze 1.1.0 as part of this slice.

## Scoring packet vs contract freeze

`identity-score-v0` fills §16 deferred items (weights, margin). It is **policy under the frozen contract**, not a new contract version.

If later voted, hash it as **slice policy freeze evidence**, alongside D-032. Do **not** bump `STASHTAB-CARD-RESOLUTION-001` to 1.0.1 or 1.1.x for this.

## Resulting contract version

**Remains `1.0.0`.** No additive amendment file.

## Files that would be hashed on a later **policy** freeze (not done now)

- `docs/card-resolution-workflow/CONTRACT.md` (already frozen 1.0.0; include as parent pin)
- `docs/card-resolution-workflow/SCORING-POLICY-INTAKE-ABSTENTION.md`
- `docs/card-resolution-workflow/freezes/PROPOSED-IDENTITY-SCORE-v0.md` (after vote, as applied freeze record)
- D-032 text in `docs/agent-context/DECISIONS.md` (citation only)

Mechanism: same SHA-256 exact-bytes pattern as notification freezes. Separate from contract version. Not applied in this action.

## Implementation still locked

No code, no JustTCG, no TCGCSV, no inventory writes, no staging enablement.
