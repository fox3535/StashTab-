# Freeze-check evidence — AMENDMENT-1.1.1

**Human vote:** APPROVE `STASHTAB-CARD-RESOLUTION-001 / AMENDMENT-1.1.1` on 2026-08-24  
**Product-policy record:** `docs/card-resolution-workflow/AMENDMENT-1.1.0.md` unchanged  
**Binding addendum recorded in 1.1.1:** D-N5 at-least-once Web Push transport  
**Manifest:** `docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`  
This evidence file does not store SHA-256 hashes of frozen bodies.

## Packet completeness

| Item | Result |
| --- | --- |
| Closed product/retention decisions D-N1–D-N4 | PASS — not reopened |
| Durable intent is transport-after-commit, not in-memory-only create | PASS — §1.18 / §7 |
| Pattern A/B named for oversale, adjust anomaly, card-resolution, security/ops, test send | PASS |
| Crash after commit cannot permanently lose the alert | PASS — sweep |
| Replay cannot duplicate occurrences | PASS — UNIQUE `(shop_id, source_kind, source_key)` |
| Transport failure never rolls back business rows | PASS |
| Notification outage cannot resolve exceptions | PASS |
| Delivery states pending / retry_scheduled / sent / failed_exhausted / expired / cancelled | PASS — §3 |
| Mixed-device and zero-device terminalization | PASS |
| Oldest-due fairness and poison containment | PASS — §4 |
| At-least-once transport; duplicate push is safe and non-mutating | PASS — D-N5 / clause 25 |
| Exactly-once not claimed | PASS |
| 1.1.0 file unmodified | PASS |
| Frontend / production VAPID / live push out of scope | PASS |

## Identity compatibility (bounded)

JWT + shop membership; shop/user headers are not credentials. Matches
fail-closed identity: verified token + membership; `X-Shop-Id` /
`X-Clerk-User-Id` untrusted. Background ticks use persisted `Shop.id`.

**Result:** GREEN

## Inventory-truth 1.2.0 compatibility (bounded)

Notification migrator is separate. Startup `create_all` does not own
notification or inventory-truth tables. Ack/resolve cannot mutate
`inventory_exception` or quantity paths. Pattern B reads durable
oversale / `adjust_anomaly` exceptions; it does not rewrite slice-03
writers. Transport failure cannot roll back sales or adjustments.

**Result:** GREEN

## Freeze recommendation

FROZEN. Implementation remains blocked until a named unlock. This freeze
does not copy code, commit, push, merge, deploy, enable Web Push, apply
migrations, or use production credentials.
