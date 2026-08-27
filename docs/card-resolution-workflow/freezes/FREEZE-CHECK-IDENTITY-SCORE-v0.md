# Freeze-check evidence — identity-score-v0

**Human vote:** APPROVE policy freeze under `STASHTAB-CARD-RESOLUTION-001` v1.0.0 §16  
**Date:** 2026-08-27  
**Manifest:** `docs/card-resolution-workflow/freezes/FREEZE-IDENTITY-SCORE-v0.json`  
This evidence file does not store SHA-256 hashes of frozen bodies.

## Completeness

| Item | Result |
|---|---|
| Contract body unedited | PASS — still version 1.0.0 |
| Notification 1.1.1 / 1.1.2 files unedited | PASS — not rewritten |
| No contract amendment | PASS — authority check |
| D-032 formula locked | PASS — integer 15/20/20/25/10/10 |
| Auto-accept only at 100 | PASS |
| Margin 10 hundredths | PASS |
| Pokémon registry; no silent default | PASS |
| Printing map exact aliases only | PASS |
| Price excluded | PASS |
| JustTCG/TCGCSV disabled | PASS |
| Inventory writes excluded | PASS |
| Manifest does not hash itself | PASS |
| One-byte tamper fails | PASS — validator `--prove-tamper` |

## Historical freeze still validates

Re-run `scripts/validate_card_resolution_contract.py` and
`scripts/validate_notification_freeze.py` after this freeze. Those packets
must remain GREEN. This policy freeze must not rewrite them.

## Terminal

Policy FROZEN. Implementation remains blocked until a **new** named unlock.
This freeze does not commit, push, deploy, migrate, call providers, or
enable staging/production.
