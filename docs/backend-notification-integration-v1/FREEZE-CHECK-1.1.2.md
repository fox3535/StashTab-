# Freeze-check evidence — AMENDMENT-1.1.2

**Human vote:** APPROVE `STASHTAB-CARD-RESOLUTION-001 / AMENDMENT-1.1.2` on 2026-08-24  
**Parents:** AMENDMENT-1.1.0 (unchanged) and AMENDMENT-1.1.1 (frozen, unchanged)  
**Manifest:** `docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`  
This evidence file does not store SHA-256 hashes of frozen bodies.

## Packet completeness

| Item | Result |
| --- | --- |
| 1.1.0 and 1.1.1 files unmodified | PASS — not rewritten by this freeze |
| Four additive tables named exactly | PASS — `notification_source_observation`, `notification_occurrence_transition`, `notification_delivery_attempt`, `notification_recovery_park` |
| Table inventory 8 frozen + 4 new = 12 | PASS — amendment §5 |
| `occurrence_count` and `last_seen_at` on `notification_event` | PASS |
| `claimed_until` and `UNIQUE (shop_id, id)` on delivery | PASS |
| Observation uniqueness `(shop_id, source_kind, source_key, observation_token)` | PASS |
| Transition seq and allowed transitions | PASS — NULL→pending; pending→delivered/failed/cancelled |
| Immutable started/outcome attempt phases | PASS |
| Lease-expiry crash recovery | PASS — `claimed_until` |
| Shop-scoped membership before send | PASS — R5 |
| Owner cancel shop-scoped 401/404/403 | PASS — R1 |
| Test-send unique identity + rate limit | PASS — R6 |
| Poison park does not hide later sources | PASS — R9 |
| Due fairness COALESCE, not NULLS FIRST | PASS — R10 |
| TLS hostname verify with IP pin | PASS — R13 |
| Post-ack occurrence finalization | PASS — §3 |
| Closed wording only | PASS |

## Identity compatibility (bounded)

JWT + current shop membership. Cross-shop cancel is 404. Membership in
another shop does not authorize send. Matches fail-closed identity.

**Result:** GREEN

## Inventory-truth 1.2.0 compatibility (bounded)

Notification migrator remains separate. Ack/resolve/cancel cannot mutate
`inventory_exception`. Reconstruction does not fabricate provider outcomes.

**Result:** GREEN

## Terminal review outcome

FROZEN after human APPROVE. Implementation remains blocked until a **new**
named unlock. The 1.1.1 unlock does not authorize 1.1.2 apply. This freeze
does not copy code, commit, push, merge, deploy, enable Web Push, apply
migrations, or use production credentials.
