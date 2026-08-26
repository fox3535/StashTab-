# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-25
**Branch:** `feature/staging-readiness-slice-00`
**Commit:** planning checkpoint `131bc1eed01f3e9b732e41cde039de6c15cea707`. **Not merged. Not deployed.**

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.0 unchanged
  product-policy record. AMENDMENT-1.1.1 **FROZEN** 2026-08-24
  (`freezes/FREEZE-1.1.1.json`). AMENDMENT-1.1.2 **FROZEN** 2026-08-24
  (`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`).
  Web Push disabled. Local 1.1.2 backend **ACCEPTED 2026-08-25**;
  merged to `main` as `c3647a4`; not deployed.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — FROZEN 2026-08-24
  (AMENDMENT-1.2.0 applied; hashes in `freezes/FREEZE-1.2.0.json`).
  Slices 01–03 accepted and included in `c3647a4`; not deployed.

## Current phase

`backend-foundation / staging-readiness-v1`
**ON `feature/staging-readiness-slice-00` — SLICE-00 CODE COMPLETED, NOT MERGED, NOT DEPLOYED.**
Owner accepted the isolated API code 2026-08-25. Planning checkpoint
`131bc1eed01f3e9b732e41cde039de6c15cea707`. No cloud resources provisioned.

Deployment gates standing: production schema apply needs human approval;
production membership unique index required first; cutover reconciliation
must equal zero; cutover runbook + audit logging + break-glass procedure
required.

**Architecture (D-024):** Convex is removed from the target stack. Clerk is
identity. FastAPI + Neon own application data. Do not provision Convex.

## Approved boundaries

- Python/FastAPI owns business logic; tenant data uses `shop_id`.
- Identity: signed token + membership. Shop header is an untrusted hint.
- Local identity bypass only when `APP_ENV` is `local` or `test` and
  `STASHTAB_ALLOW_DEV_IDENTITY` is set.
- Humans approve production writes, contract changes, Web Push, payments,
  Watch, inventory-truth unlock, and this identity acceptance.

## Active gates

1. ~~Human acceptance of the identity slice.~~ **Completed 2026-08-23.**
2. ~~AMENDMENT-1.1.1 and AMENDMENT-1.1.2 frozen.~~ Local 1.1.2 backend
   **accepted 2026-08-25**. PR #1 **merged** at `c3647a4`. **NOT DEPLOYED**.
   **NOTIFICATION-INTEGRATION-GATE** is **closed for backend overlap only**.
   Frontend settings/service-worker, production VAPID, and production
   migrator/roles/cutover remain open. Authenticated API transport for
   existing admin/POS callers is on `main`.
3. `slice-02-outbound-events` **accepted** and on `main` via `c3647a4`
   (not deployed). **MIGRATOR-ROLE-PROVISIONING-GATE** still blocks
   production schema apply/deploy.
4. `slice-03-adjustments` **accepted** and on `main` via `c3647a4`
   (not deployed). **CSV-COST-FEEDBACK-GATE** blocks production CSV adjust use.
5. `card-resolution-core-v1` build blocked.
6. `security-assurance-v1` implementation blocked.
7. Production schema apply (inventory truth + identity index +
   notification schema) blocked on human approval plus standing
   deployment gates. Production VAPID / live Web Push remains disabled.

## Next queued phases

1. Draft PR review of slice-00 code, then a separate named unlock to
   provision isolated Railway + Neon + Clerk. Do not provision from
   the freeze or this code acceptance.
2. Remaining frontend notification settings / production gates.
3. `card-resolution-core-v1` — planning allowed, build blocked.
