# Slice-01 identity schema and identity smoke — acceptance

**Slice:** `staging-readiness-v1 / slice-01-base-schema-and-identity-smoke`  
**Status:** `COMPLETED, DEPLOYED TO STAGING ONLY`  
**Decision:** APPROVED by named human owner 2026-08-26  
**This file is not in the freeze hashes.** Frozen packet files were not rewritten.

## Deployed evidence

| Item | Value |
| --- | --- |
| Railway API deploy | `17aeb85f-053f-4e5a-8d68-6d040d03c238` |
| Deployed API Git SHA | `0dd8f00b8d510b82e3d717a9570c0bc387e0479b` |
| Current `main` | `fe3b2cfb9903050eef45bcf434ef8a0ddafdb3e8` |
| Neon application tables | `shops`, `shop_members` only |
| Synthetic shops | two (`smoke-shop-a`, `smoke-shop-b`) |
| Synthetic Clerk owners | two distinct users, one owner each |

## Identity smoke accepted

- Anonymous shop create rejected
- Spoofed user headers without a bearer token rejected
- Shop and owner membership committed in one transaction
- Duplicate slug rejected; no extra shop row
- User A own shop 200; other shop 403
- User B own shop 200; other shop 403
- Duplicate membership 409 without database error detail
- Health and readiness 200
- Desktop helper files used during the smoke were removed afterward
- Tokens, cookies, verification codes, and credentials were not captured

## Explicitly not in this acceptance

Shopify, inventory schema, notifications, worker, Web Push, payments, production, Convex, or any later slice unlock.

Convex is out of architecture under D-024. Frozen staging text that still says “Convex deferred” is historical.

## Next proposed checkpoint (planning only)

`staging-readiness-v1 / slice-02-inventory-schema-rehearsal`  
See `PLAN-SLICE-02-INVENTORY-SCHEMA-REHEARSAL.md`. Not approved, not unlocked, not executed.
