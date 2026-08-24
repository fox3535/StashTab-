# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-24
**Branch:** `feature/inventory-truth-slice-03` (isolated worktree; not merged)
**Commit:** local slice-03 checkpoint pending; base planning `6370060`

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. AMENDMENT-1.1.0 unchanged
  product-policy record. AMENDMENT-1.1.1 **FROZEN** 2026-08-24
  (`docs/backend-notification-integration-v1/freezes/FREEZE-1.1.1.json`).
  Web Push disabled. Backend implementation awaiting named unlock.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.2.0** — FROZEN 2026-08-24
  (AMENDMENT-1.2.0 applied; hashes in `freezes/FREEZE-1.2.0.json`).
  Slice-03 accepted 2026-08-24; not merged, not deployed. Slice-02 accepted;
  not merged, not deployed.

## Current phase

`inventory-truth-v1 / slice-02-outbound-events` **COMPLETED — NOT MERGED
— NOT DEPLOYED** (human acceptance 2026-08-24; see
`docs/inventory-truth-v1/ACCEPTANCE-SLICE-02.md`). Slice-01 remains
completed and not deployed. Next queued planning packet:
`slice-03-adjustments` **COMPLETED — NOT MERGED — NOT DEPLOYED**. Notification
work stays in the main working tree behind **NOTIFICATION-INTEGRATION-GATE**.

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
2. AMENDMENT-1.1.1 frozen. Named `implementation_unlock` required before
   backend notification code. Web Push remains disabled.
3. `slice-02-outbound-events` **accepted 2026-08-24** (not merged, not
   deployed). **NOTIFICATION-INTEGRATION-GATE** and
   **MIGRATOR-ROLE-PROVISIONING-GATE** block merge/schema-apply/deploy.
4. `slice-03-adjustments` **accepted 2026-08-24** (not merged, not
   deployed). **CSV-COST-FEEDBACK-GATE** blocks production CSV adjust use.
5. `card-resolution-core-v1` build blocked.
6. `security-assurance-v1` implementation blocked.
7. Production schema apply (inventory truth + identity index) blocked on
   human approval plus standing deployment gates.

## Next queued phases

1. Named implementation unlock for frozen backend-notification 1.1.1
   (do not start from this freeze).
2. Notification integration with slice-02 overlapping files before any
   merge.
3. `card-resolution-core-v1` — planning allowed, build blocked.
