# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-25
**Branch:** `feature/backend-notification-v1.1.2` (isolated worktree; not pushed)
**Commit:** local 1.1.2 implementation checkpoint pending on this branch

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.0 unchanged
  product-policy record. AMENDMENT-1.1.1 **FROZEN** 2026-08-24
  (`freezes/FREEZE-1.1.1.json`). AMENDMENT-1.1.2 **FROZEN** 2026-08-24
  (`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.2.json`).
  Web Push disabled. Local 1.1.2 backend **ACCEPTED 2026-08-25**; not
  pushed, not merged, not deployed.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — FROZEN 2026-08-24
  (AMENDMENT-1.2.0 applied; hashes in `freezes/FREEZE-1.2.0.json`).
  Slice-03 accepted 2026-08-24; not merged, not deployed. Slice-02 accepted;
  not merged, not deployed.

## Current phase

`backend-notification-integration-v1 / implementation-1.1.2`
**COMPLETED — NOT PUSHED — NOT MERGED — NOT DEPLOYED** (human acceptance
2026-08-25; see `docs/backend-notification-integration-v1/ACCEPTANCE-1.1.2.md`).
Identity, receive, outbound, and adjustment backend slices are present on
this branch. Merge waits for **GITHUB-NOTIFICATION-CI-GATE**.

Deployment gates standing: production schema apply needs human approval;
production membership unique index required first; cutover reconciliation
must equal zero; cutover runbook + audit logging + break-glass procedure
required.

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
   **accepted 2026-08-25**. **GITHUB-NOTIFICATION-CI-GATE** blocks merge and
   deployment until GitHub runs the blocking PostgreSQL notification
   workflow on the exact pushed commits.
3. `slice-02-outbound-events` **accepted 2026-08-24** (not merged, not
   deployed). **NOTIFICATION-INTEGRATION-GATE** and
   **MIGRATOR-ROLE-PROVISIONING-GATE** block merge/schema-apply/deploy.
4. `slice-03-adjustments` **accepted 2026-08-24** (not merged, not
   deployed). **CSV-COST-FEEDBACK-GATE** blocks production CSV adjust use.
5. `card-resolution-core-v1` build blocked.
6. `security-assurance-v1` implementation blocked.
7. Production schema apply (inventory truth + identity index +
   notification schema) blocked on human approval plus standing
   deployment gates. Production VAPID / live Web Push remains disabled.

## Next queued phases

1. Owner authorization to push `feature/backend-notification-v1.1.2` for
   remote CI.
2. **GITHUB-NOTIFICATION-CI-GATE** must pass on those exact commits.
3. `card-resolution-core-v1` — planning allowed, build blocked.
