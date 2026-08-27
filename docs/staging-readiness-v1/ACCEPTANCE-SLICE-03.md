# Slice-03 authenticated inventory read smoke — staging acceptance

**Slice:** `staging-readiness-v1 / slice-03-authenticated-inventory-read-smoke`  
**Status:** `COMPLETED, STAGING ONLY`  
**Decision:** D-029  
**Accepted:** named human owner 2026-08-27  
**Pinned API:** Railway deploy `17aeb85f-053f-4e5a-8d68-6d040d03c238` at Git SHA `0dd8f00b8d510b82e3d717a9570c0bc387e0479b`  
**Code on `main`:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

## Accepted staging evidence

| Item | Result |
| --- | --- |
| Health / ready | 200; staging; notifications, web push, Shopify, worker off; inventory cutover false |
| Public tables | exact 13: `shops`, `shop_members`, `inventory_item`, `purchase_record`, `sale`, `acquisition_lot`, `inventory_event`, `inventory_truth_cutover`, `inventory_channel_observation`, `refund_record`, `return_record`, `inventory_exception`, `inventory_adjustment` |
| Inventory tables | remained empty |
| `stashtab_api` | SELECT allowed on new tables; INSERT denied |
| Worker / readonly grants | not visible to the API role; recorded from D-028 schema-apply evidence |
| No token / spoofed headers | 401 |
| Own-shop search | each owner 200 empty |
| Cross-shop | 403 |
| CSV quantity | controlled 503 `FEATURE_NOT_READY` |
| PATCH quantity | 404; empty table; **not** a passed write-guard |
| Checkout | 400 unknown SKU; lookup before mutation gate; **not** a passed write-guard |
| Intake | unused; extra live table intentionally absent |
| Data / flags | no data changed; background and external features stayed off |

Clerk tokens were minted in memory and not saved. No Railway login, migrator role, seed, or schema change.

## Explicitly not accepted

Inventory writes, intake, POS, adjust, CSV quantity as a working write path,
Shopify, worker, notifications, Web Push, payments, Watch, production,
dual-write, or cutover complete.

PATCH, checkout, and intake remain **future write-enablement gates**. They
are not passed. Do not seed inventory merely to finish those probes.

## Next proposed checkpoint (planning only)

`card-resolution-core-v1 / slice-01-intake-abstention`  
See `docs/card-resolution-workflow/PLAN-SLICE-01-INTAKE-ABSTENTION.md`.
Not approved, not unlocked, not implemented.
