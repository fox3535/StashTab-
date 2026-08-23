# Current context

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` (active); `STASHTAB-CARD-RESOLUTION-001` (frozen)
**Last verified:** 2026-08-20  
**Branch:** `feature/card-resolution-notifications`  
**Commit:** none; working tree is uncommitted  
**Last Git object:** `e5ed96b43234b0816d3320a69ae6fd0ddc2ded22`

## Frozen contracts

- `STASHTAB-CARD-RESOLUTION-001` v1.0.0. Amendment 1.1.0 proposed; Web
  Push disabled.
- `STASHTAB-INVENTORY-TRUTH-001` **v1.1.0** — FROZEN 2026-08-23
  (AMENDMENT-1.1.0 applied; slice-02 plan frozen, implementation
  awaiting named approval).

## Current phase

`inventory-truth-v1 / slice-01-receive-foundation` **COMPLETED — NOT
DEPLOYED** (human acceptance 2026-08-23; see
`docs/inventory-truth-v1/ACCEPTANCE-SLICE-01.md`). Proposed directive for
`slice-02-outbound-events` is prepared and awaiting planning approval —
no implementation. Notification P1 leftovers remain unfixed and out of
scope.

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
2. Human freeze before amendment 1.1.0 or Web Push.
3. `slice-02-outbound-events`: AMENDMENT-1.1.0 **approved and applied**
   (contract v1.1.0, hashes in CONTRACT §8); seven binding owner
   interpretations recorded; integrity check 5/5; slice-02 plan
   **FROZEN**; implementation directive prepared and awaiting named
   approval (`DIRECTIVE-SLICE-02-IMPLEMENTATION.md`).
4. `card-resolution-core-v1` build blocked.
5. `security-assurance-v1` implementation blocked.
6. Production schema apply (inventory truth + identity index) blocked on
   human approval plus standing deployment gates.

## Next queued phases

1. Human planning-approval decision for `DIRECTIVE-SLICE-02.md`.
2. Later inventory-truth slices (adjust/stock-overwrite unlock) need new
   unlocks.
3. `card-resolution-core-v1` — planning allowed, build blocked.
