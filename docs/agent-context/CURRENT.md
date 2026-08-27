# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-26
**Branch:** `main` `fe3b2cfb9903050eef45bcf434ef8a0ddafdb3e8`
**Staging API:** Railway deploy `17aeb85f-053f-4e5a-8d68-6d040d03c238` at Git SHA `0dd8f00b8d510b82e3d717a9570c0bc387e0479b`

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.0 unchanged
  product-policy record. AMENDMENT-1.1.1 **FROZEN** 2026-08-24
  (`freezes/FREEZE-1.1.1.json`). AMENDMENT-1.1.2 **FROZEN** 2026-08-24
  (`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`).
  Web Push disabled. Local 1.1.2 backend **ACCEPTED 2026-08-25**;
  merged to `main` as `c3647a4`; not deployed to production.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — FROZEN 2026-08-24
  (AMENDMENT-1.2.0 applied; hashes in `freezes/FREEZE-1.2.0.json`).
  Slices 01–03 accepted and included in `c3647a4`; not deployed to production.

## Current phase

`backend-foundation / staging-readiness-v1`
**Slice-01 identity schema and identity smoke: COMPLETED, DEPLOYED TO STAGING ONLY (D-025).**
Neon application tables: `shops`, `shop_members` only. Two synthetic shops
with two distinct Clerk owners. Identity smoke passed (own 200 / other 403
both users; duplicate membership 409; anonymous and spoofed headers
rejected; duplicate slug rejected; atomic shop+owner; health/ready 200).
No Shopify, inventory, notifications, worker, Web Push, payments, or
production activity. Convex is out of architecture (D-024).

Production schema apply remains blocked. Slice-00 isolated API code is
on `main` via later merges; staging is the only live deploy.

## Approved boundaries

- Python/FastAPI owns business logic; tenant data uses `shop_id`.
- Identity: signed token + membership. Shop header is an untrusted hint.
- Local identity bypass only when `APP_ENV` is `local` or `test` and
  `STASHTAB_ALLOW_DEV_IDENTITY` is set.
- Humans approve production writes, contract changes, Web Push, payments,
  Watch, inventory-truth unlock, and later staging slices.

## Active gates

1. Identity smoke on staging: **closed** (D-025).
2. Production schema apply still blocked (migrator role, recon, human
   approval, CSV cost feedback, production VAPID).
3. `card-resolution-core-v1` build blocked.
4. `security-assurance-v1` implementation blocked.
5. Worker, Shopify, notifications, Web Push remain off on staging.

## Next queued phases

1. **Proposed only:** `staging-readiness-v1 / slice-02-inventory-schema-rehearsal`
   (`PLAN-SLICE-02-INVENTORY-SCHEMA-REHEARSAL.md`). Not approved, not unlocked.
2. Remaining frontend notification settings / production gates.
3. `card-resolution-core-v1` — planning allowed, build blocked.
