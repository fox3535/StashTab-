# Consistency check — scoring policy vs freeze path

**Inputs:** frozen `STASHTAB-CARD-RESOLUTION-001` v1.0.0; D-030; D-031; D-032;
`SCORING-POLICY-INTAKE-ABSTENTION.md`; examples E1–E14.  
**Pin:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**Budget:** one check, one correction. Not a freeze.

## Checks

| Requirement | Result |
|---|---|
| Auto-accept only at S=100 (all six exact) | Pass. Weights make `>= 0.95` identical to 1.00. |
| Ties / two DB rows with same six fields | Abstain (E12, D-032.8). |
| Missing language or printing | Abstain (E3). |
| Missing or unsupported game | Reject (E7, E8). No silent Pokémon default. |
| Game mismatch, no eligible Pokemon row | Reject (E9). |
| Set/collector vs name | No accept (E6 abstain). |
| Fuzzy only retrieves | E4 abstain. RapidFuzz ≥80 rejected (D-031). |
| JustTCG / TCGCSV off | Pass. Not identity resolvers. |
| No inventory mutation | Pass (D-030). Identity accept ≠ inventory. |
| Timeout / scorer fail / agent disagreement | Abstain, never accept (E11). |
| Price excluded | E5. |
| Printing ineligibility only via versioned map | E2 vs E14. |
| Closed scoring decisions | Pass after correction below. |

## Contract notes (not blockers)

- Policy is **stricter** than §5 `>= 0.95` (requires 1.00 and all six fields).
- Ambiguous band does not call JustTCG (budget/feature off). Abstain. Allowed
  as fail-closed disable of lookup (contract §15 / D-030).
- Invariant 5 (conflicting **stable identifiers**) stays **abstain** (human
  review). That is distinct from unsupported-game **reject**.

## Correction

First draft treated every “no eligible candidate” as reject. That would
turn a Pokémon Base #4 / Blastoise typo into reject instead of review.
Correction: **reject** only for missing/unsupported game or game mismatch
with no eligible row of the requested game. Well-formed field clashes
(name vs number) **abstain**. Recorded in the policy §5 and E6.

## Freeze recommendation

Scoring choices are closed. Prepare
`freezes/PROPOSED-IDENTITY-SCORE-v0.md` for an owner freeze **vote**.
Do not write freeze hashes or implement until that vote.
