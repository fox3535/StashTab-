# Prerequisite my-shop memberships read — local acceptance

**Slice:** `frontend-recovery-v1 / prerequisite-my-shop-memberships-read-v1`  
**Status:** `MERGED ON main via PR #15 — NOT DEPLOYED`  
**Decision:** D-037  
**Accepted:** named human owner 2026-08-27  
**Pinned pre-merge `main`:** `09c1e6aba03f4a075159cdbdbddf61aa85157340`  
**Merge commit:** `af72bac501cd9c42b70cd0347f778db388c8c943`  
**Route:** `GET /api/v1/shops/me/memberships`  
**This file is not in freeze hashes.** Frozen contracts were not rewritten.

## Accepted local evidence

| Item | Result |
| --- | --- |
| Clerk bearer | required; missing or invalid token → 401 |
| Identity source | verified token only; spoofed user header without token → 401 |
| Shop selection | not required to list memberships |
| Shop hint | cannot add, hide, or replace authorized memberships |
| Zero memberships | `200 {"shops":[]}` |
| One / many memberships | only the caller’s shops |
| Response fields | only `id`, `name`, `role` |
| Roles | `owner` and `staff` only |
| Ordering | normalized shop name, then shop id |
| Corrupt duplicate, missing shop, invalid role | generic 403, no database detail |
| Unrelated database errors | not mapped to authorization failures |
| `GET /api/v1/shops/me` | unchanged |
| Writes / schema | none |
| SQLite identity/API regression | 245 passed |
| Frontend slice-01 | still locked |

## Explicitly not accepted

Deploy, migrate, frontend slice-01 implementation, inventory writes,
notifications, workers, payments, or Watch.
