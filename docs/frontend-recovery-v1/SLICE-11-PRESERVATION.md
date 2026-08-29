# Slice-11 inventory reconciliation status — preservation record

**Slice:** `frontend-recovery-v1 / slice-11-inventory-reconciliation-status`
**Base:** `main` `96fe2a7`
**Status:** draft PR, not merged, not deployed.
**Contracts:** accepted authenticated read routes in
`services/api/app/routers/admin.py`, both audited before implementation:

- `GET /api/v1/admin/inventory-truth/status` (`inventory_truth_status`):
  returns `shop_id`, `cutover_status` (`null` when no cutover row
  exists), and `unaccounted` (the reconcile mismatch map).
- `GET /api/v1/admin/inventory-truth/reconcile`
  (`inventory_truth_reconcile`): returns `shop_id`, `unaccounted_qty`,
  and `mismatches` mapping SKU → `{ event_remaining, snapshot_stock }`
  (`snapshot_stock` is `null` when the SKU has no inventory snapshot
  row). Empty truth/inventory tables yield zero mismatches.

Both use `get_shop_context` (verified Clerk bearer + `require_membership`;
`X-Shop-Id` is an untrusted hint). Authorization is any shop member
(owner or staff); the owner-only gate (`_require_owner`) exists only on
the cutover POST, which this slice never calls. Both endpoints are pure
SELECTs over `inventory_truth_cutover` (shop_id, status),
`inventory_event` (shop_id, sku, quantity_delta), and `inventory_item`
(shop_id, sku, stock) — every table present in the approved staging
schema, with SELECT-only grants to `stashtab_api` enforced by
`inventory_live_schema/migrator.py` `apply_rehearsal`. Neither endpoint
writes, locks cutover state, repairs data, starts backfill, or changes
inventory. Reconciliation semantics follow frozen inventory-truth-v1
`DESIGN.md` §1 recon (event-derived remaining must equal snapshot
stock). All filters are shop-scoped; returned identifiers are the shop's
own SKUs, so no cross-shop data risk. The reconcile map is uncapped, so
the check runs only through an explicit labeled control with a 15-second
client timeout; a timed-out or failed check is stated plainly, never
presented as green.

## What was added

- Read-only **Inventory Integrity** screen replacing the locked legacy
  Collectr CSV stub at `app/admin/reconciliation/page.tsx` (POST upload,
  CSV export, price-drift actions). None of that behavior is revived.
- Pure helpers in `lib/inventory-integrity.ts`:
  `INTEGRITY_CHECK_TIMEOUT_MS` (15000), `describeCutoverStatus`,
  `reconOutcomeText`, `formatMismatchValue`, and `timedOutNotice`.
  Missing values render as an honest "—"; zero mismatches is reported
  as what the check returned, not as a permanent guarantee.
- Client wrappers `mimirApi.inventoryTruthStatus` /
  `mimirApi.inventoryTruthReconcile` + types in `lib/mimir-api.ts`,
  read-only GETs only.
- Status is shown separately from reconciliation results. The check
  never runs automatically — only through the labeled "Run read-only
  check" control. Cutover-off stays visible and is neither an error nor
  an approval. States distinguished: idle, running, matched, mismatched,
  timed out, and failed (401/403/503/network via `classifyVendorError`).
- Shop switching clears all results immediately and aborts in-flight
  checks; epoch + `shouldApplyShopResult` + AbortController guards
  reject late responses.
- Sidebar entry renamed/unlocked ("Inventory Integrity", ShieldCheck)
  and an honest dashboard card added. No production-readiness metric.
- `components/vendor/locked-route-gate.tsx`: removed `/admin/reconciliation`
  (this slice) and also `/admin/reports` — a pre-existing latent defect
  where slice-09's merged Recent Trade History screen was still
  gate-locked since slice-01. This is a lock-list correction only; no
  other route state changed.

## Read-only by construction

No repair, reconcile-write, cutover transition, backfill, adjustment,
receive, sale, CSV, upload, export, Shopify, notification, payment, or
Watch capability exists in the touched code. All remaining locked routes
(intake, staging, resticker, paperweight, Shopify, imports, settings)
stay locked.

## Preserved and untouched

- Membership authority, Clerk bearer auth, selected-shop hint behaviour,
  and every prior slice's behaviour (all 123 tests across twelve suites
  pass; 12 new slice-11 tests; dashboard-link expectations extended to
  the sixth honest tool).
- No backend, schema, API contract, cloud configuration, env file,
  secret, barcode artifact, or frozen document changed. No seed data,
  staging writes, or deployments. Test fixtures are clearly labeled
  synthetic data; staging may only prove the honest no-cutover /
  zero-mismatch states.
