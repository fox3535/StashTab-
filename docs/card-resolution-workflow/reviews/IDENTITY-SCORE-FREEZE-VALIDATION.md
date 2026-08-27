# Freeze validation — identity-score-v0

**Manifest:** `freezes/FREEZE-IDENTITY-SCORE-v0.json` (not hashed)  
**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0 (body unedited)

| Check | Result |
|---|---|
| Manifest not in files[] | PASS |
| Relative paths only; no `..` or absolute | PASS |
| No duplicate paths | PASS |
| SHA-256 of LF-normalized bytes | PASS |
| One-byte tamper changes digest | PASS `--prove-tamper` |
| Contract version still 1.0.0 | PASS |
| Notification 1.1.1 git-canonical freeze | GREEN |
| Notification 1.1.2 git-canonical freeze | GREEN |
| `validate_card_resolution_contract.py` | PASS |
| Implementation unlocked | false |

**Outcome:** policy freeze valid. Implementation not authorized.
