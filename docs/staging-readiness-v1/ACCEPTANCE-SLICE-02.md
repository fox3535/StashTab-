# Slice-02 inventory schema rehearsal — staging acceptance

**Slice:** `staging-readiness-v1 / slice-02-inventory-schema-rehearsal`  
**Status:** `COMPLETED, APPLIED TO STAGING ONLY`  
**Decision:** D-027 table set; local implementation merged as PR #12; staging Neon
apply verified 2026-08-27  
**Code on `main`:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**This file is not in freeze hashes.** Frozen packet files were not rewritten.

## Verified staging evidence

| Item | Result |
| --- | --- |
| Database | Neon `stashtab_staging` as `stashtab_migrator` |
| Starting state | `shops`, `shop_members` only |
| Final public tables | 13 exact tables |
| Live parents | `inventory_item`, `purchase_record`, `sale` |
| Truth tables | `acquisition_lot`, `inventory_event`, `inventory_truth_cutover`, `inventory_channel_observation`, `refund_record`, `return_record`, `inventory_exception`, `inventory_adjustment` |
| Idempotent rerun | both migrators created zero new objects |
| Ownership | all 11 new tables owned by `stashtab_migrator` |
| `stashtab_api` | SELECT only on new tables |
| Worker, readonly, PUBLIC | no privileges on new tables |
| Shop FKs / unique `(shop_id, id)` | present on all three live parents |
| `sale.show_session_id` | nullable, no foreign key |
| Cross-shop lot insert | rejected |
| Identity | two shops (`smoke-shop-a`, `smoke-shop-b`), two owners, unchanged |
| New tables empty | yes |
| Rollback | not required |

Railway was not contacted. No Clerk, production, seed, or route enablement.

## Explicitly not in this acceptance

Inventory, intake, POS, adjust, CSV quantity, Shopify, worker, notifications,
Web Push, payments, Watch, production, dual-write, or cutover.

## Next proposed checkpoint (planning only)

`staging-readiness-v1 / slice-03-inventory-readonly-search`  
See `PLAN-SLICE-03-INVENTORY-READONLY-SEARCH.md`. Not approved, not unlocked.
