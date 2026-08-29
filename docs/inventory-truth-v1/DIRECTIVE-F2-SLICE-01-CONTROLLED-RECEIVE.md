# Proposed directive — F2 slice-01 controlled staging receive

**Status:** `PROPOSED — PLANNING ONLY — IMPLEMENTATION BLOCKED`
**Bound by:** `STASHTAB-INVENTORY-TRUTH-001 / AMENDMENT-1.3.0`
(`PROPOSED — NOT APPROVED — NOT FROZEN`) and
`docs/frontend-recovery-v1/PLAN-F2-SLICE-01-CONTROLLED-RECEIVE.md`
**Pinned branch:** `planning/f2-controlled-receive-amendment-1.3.0`
**Does not authorize implementation, schema apply, privilege change,
cutover, merge to `main`, or deploy.**

This directive binds any future implementation of the F2 controlled
receive to the proposed amendment as its sole contract surface. If the
amendment is rejected or amended by vote, this directive is void and a
new directive is required.

## 1. Unlock sequence (all four required, in order)

1. Human vote approves AMENDMENT-1.3.0; freeze applied exactly per its
   §15 (non-self-hashing manifest `FREEZE-1.3.0.json`; validator green).
2. **Implementation unlock (named):** endpoint, controlled-503 handler,
   model column, migrator changes, tests — on a focused branch from
   frozen `main`, per §2–§5 below.
3. **Provisioning unlock (named):** reviewed migrator apply on staging
   Neon only (column, partial unique, grants, policy assert); migrator
   role only; runtime role never applies schema.
4. **Cutover unlock (named):** gen-1 cutover on the synthetic shop per
   amendment §9, owner actor, pre-checks and acceptance-recorded actor
   evidence.

No unlock may be inferred from another. No production unlock exists.

## 2. Allowed implementation work (after unlock 2 only)

- New route `POST /api/v1/admin/inventory/receive` exactly per
  amendment §5: request/response fields, validation, status codes,
  one-transaction sequence, generic failures.
- One FastAPI exception handler mapping `InsufficientPrivilege` and
  `ProgrammingError` (undefined table) to 503 `FEATURE_NOT_READY`
  (amendment §8).
- `PurchaseRecord.client_idempotency_key` ORM column (nullable) and
  reviewed live-migrator steps in amendment §4 order.
- Grant/policy-assert changes in the live migrator exactly per
  amendment §7; `_assert_select_only` becomes the per-table policy
  assert for staging only.
- Tests: the amendment §13 list (PostgreSQL twice on fresh disposable
  databases + API-level equivalents), plus local SQLite regressions.

## 3. Authorization binding

- Receive: verified Clerk bearer + `require_membership`; `owner` or
  `staff`. No dev bypass in staging (fail-closed identity behavior,
  D-025). First staging smoke uses an owner.
- Cutover: owner-only gate unchanged.
- No frontend-only role restriction is introduced; no frontend receive
  UI exists in this slice.

## 4. Concurrency and replay binding

- Commit only at the end of the transaction; a losing concurrent
  request rolls back its ENTIRE transaction (including any item insert)
  before reloading the winner and returning `no_op`.
- Replay resolution is by `(shop_id, client_idempotency_key)` only;
  payload-equality is the SHA-256 digest of `(sku, quantity,
  unit_cost)` recomputed from the stored purchase row; mismatch → 409,
  zero writes.
- The duplicate-`(shop_id, sku)` race on concurrent first receives
  with DIFFERENT client keys is documented accepted parity with the
  trade-apply path; no unique `(shop_id, sku)` is added.

## 5. Hard exclusions (implementation must not touch)

Shopify, workers, notifications, payments, Watch, price approval,
`sync_outbox`, CSV, trade UI, checkout, sales writes, quantity
adjustments, seed scripts, direct manual inserts, frontend receive UI,
frozen document bodies, production configuration.

## 6. Acceptance gates (all required before slice acceptance)

1. Amendment §13 tests 1–8 green, PG twice on fresh databases.
2. Reconciliation zero after receive; timeout never green.
3. Unrelated routes after cutover return controlled 503, never raw
   privilege/undefined-table 500 (test 7).
4. Runtime role boundary proven (test 1), including `SET ROLE
   stashtab_migrator` denied.
5. `F2-TEST-0001` retained as labeled staging proof; retention recorded
   in the acceptance document.

## 7. Bounded correction rule

One review + at most one correction pass per stage (implementation,
provisioning, cutover). A timeout or repeated review is not success and
stops with one named blocker. No endless gate loops.
