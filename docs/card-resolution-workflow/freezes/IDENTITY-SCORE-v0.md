# Frozen policy — identity-score-v0

**Status:** `FROZEN` (policy detail under contract §16)  
**Contract:** `STASHTAB-CARD-RESOLUTION-001` **v1.0.0** (unchanged; no amendment)  
**Ruleset:** `identity-score-v0`  
**Maps:** `language-map-v0`, `printing-map-v0`, `norm-v0` (in scoring policy)  
**Game registry:** `pokemon` only  
**Margin:** 10 hundredths  
**Decisions:** D-030, D-031, D-032  
**Manifest:** `docs/card-resolution-workflow/freezes/FREEZE-IDENTITY-SCORE-v0.json` (not hashed)

## Contract authority (not an amendment)

Exact unique local identity accept without an external request is already
authorized by frozen `CONTRACT.md`:

- §1 hierarchy (full pipeline; lookup not required on every intake)
- §5 exact local match (`>= 0.95`, unique, no conflicts)
- §6 JustTCG only for ambiguous/enrichment/price cases
- §7 human review for conflicts, multiples, missing evidence
- §8 `external_validation_pending` optional
- §13.1 unique `>= 0.95` local match accepted without an external request
- §15 emergency disable of lookup is a safety action

D-032 is stricter (`S = 100`, six exact fields, margin ≥ 10). That does not
weaken v1.0.0.

The planning sentence that an amendment is required for auto-accept
without JustTCG referred to the **ambiguous band**, not D-032.

## Locked scoring (D-032)

Integer hundredths. Auto-accept only at total 100.

- Weights: game 15, set 20, collector number 20, normalized name 25,
  language 10, printing 10
- All six mandatory fields present and exact
- Exactly one eligible canonical identity
- Margin `winner - runner_up >= 10`
- Omitted printing or language → abstain
- Two DB rows matching all six fields → abstain
- Missing/unsupported game → reject; no silent Pokémon default
- Named printing ineligibility only via `printing-map-v0`
- `norm-v0` format-only; fuzzy is not equality
- Price/market excluded
- RapidFuzz retrieve-only
- JustTCG and TCGCSV disabled

## This freeze does not authorize

Implementation; staging or production schema; external API calls; JustTCG
credits; TCGCSV ingest; inventory writes or promotion; AI identity
confidence; fuzzy auto-accept; games beyond Pokémon; notification or
frontend work.

## Implementation

Still locked until a separate named unlock. Prepared (not executed) directive
may exist alongside this freeze.
