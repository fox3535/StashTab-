# Proposed freeze — identity-score-v0

**Status:** `SUPERSEDED` by `IDENTITY-SCORE-v0.md` / D-033. Not hashed.  
**Vote required before freeze hashes or implementation.**  
**Ruleset:** `identity-score-v0`  
**Maps:** `language-map-v0`, `printing-map-v0`, `norm-v0`  
**Game registry:** `pokemon` only  
**Margin:** 10 hundredths (`winner - runner_up >= 10`)  
**Authority:** D-030, D-031, D-032; parent contract `STASHTAB-CARD-RESOLUTION-001` v1.0.0  
**Does not amend** the frozen contract. Authority for no-JustTCG
auto-accept on unique exact local match is already `CONTRACT.md` §5 and
§13.1 (`reviews/DETERMINISTIC-ACCEPT-AUTHORITY-CHECK.md`). This packet
only records D-032 weights/margin under §16.

## Scope of this freeze (if voted)

Locks for slice-01 intake/abstention:

- Integer identity formula and weights (15/20/20/25/10/10).
- Auto-accept only at total **100**, all six fields present and exact,
  one eligible canonical identity, margin ≥ 10.
- Omitted printing or language → abstain.
- Duplicate six-field DB identities → abstain.
- Missing/unsupported game → reject; no silent Pokémon default.
- Named printing ineligibility only via `printing-map-v0` exact aliases.
- `norm-v0` format-only rules (no fuzzy-as-equal).
- Price/market excluded from eligibility and `S`.
- JustTCG and TCGCSV remain disabled; not identity resolvers.
- Identity `accepted` is not inventory write.
- RapidFuzz may retrieve candidates only.

## Implementation exclusions (still locked after freeze)

- Any code, local DDL, staging Neon DDL, HTTP routes, or tests execution
  until a **named implementation unlock**.
- JustTCG client, credits, cache, or identity fallback.
- TCGCSV ingest or candidate use.
- Inventory, lot, event, price, sale, purchase, Shopify, payment, Watch,
  notification delivery.
- OCR, CSV import identity, review UI.
- Expanding the game registry.
- Adding printing/language aliases beyond v0 maps (that is a map
  version bump, not silent inference).
- Partner snapshot update (`b798bf0` stays).

## Remaining non-scoring items (not freeze blockers)

Named implementation unlock: tests-only vs HTTP; who may `decide` on
review rows. Provider spikes and inventory promotion stay later slices.

## How to apply later (do not do this now)

On freeze vote: record freeze hash of this file + maps, set policy status
to `FROZEN`, and still require a separate implementation unlock before code.
