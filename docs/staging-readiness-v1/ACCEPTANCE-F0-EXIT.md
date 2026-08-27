# F0 backend-foundation exit — frontend recovery

**Status:** `PASSED FOR FRONTEND RECOVERY`  
**Decision:** D-035  
**Pinned `main`:** `6a266b10639df2931e1bd37d4040b49a0efd0bd2`  
**PR:** #13 merged 2026-08-27  
**This file is not in freeze hashes.**

This is not production approval. Inventory writes, notifications, Shopify,
payments, Watch, workers, and Web Push stay disabled.

## Recorded evidence

| Criterion | Result |
|---|---|
| Fail-closed identity / shop isolation | D-025 staging smoke |
| Inventory schema | D-028 staging apply, 13 tables, API SELECT only |
| Inventory read contract | D-029 authenticated empty search, cross-shop 403 |
| Card-resolution intake/abstention | D-034; merged PR #13; feature off |
| Notification isolation | Local/PostgreSQL 1.1.2 accepted on `main`; live push off |
| Foundation P0/P1 | None block read-only UI integration |
| Frontend test loop | Clerk middleware + FastAPI bearer/shop-header contract |

## Explicitly not approved

Production deploy, staging card-resolution migrate, feature-flag on,
inventory write enablement, notification staging apply, live Web Push,
Shopify, payments, Watch.

## Next

Frontend recovery planning: `docs/frontend-recovery-v1/`.
First proposed implementation slice after owner approval:
authenticated shell + read-only inventory.
