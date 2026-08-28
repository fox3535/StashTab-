# Slice-06 admin inventory full browse — preservation record

**Slice:** `frontend-recovery-v1 / slice-06-admin-inventory-full-browse`  
**Base:** `main` `628f470` (merge commit of PR #22 / slice-05)  
**Contract:** accepted authenticated `GET /api/v1/inventory/search`
(D-029 read-ready; exact barcode/SKU priority, `total`, `offset`/`limit`
with `limit ≤ 100`, shop-scoped, in-stock only). No backend change; empty
`q` returns the full in-stock browse.

## What was recovered on `/admin/inventory`

- Honest total: the header count comes from the contract `total`, never
  from the current page length. Before the first response lands it reads
  "counting…"; on a classified error it reads "total unavailable" — a
  broken read is never presented as a verified zero.
- Offset pagination (50 per page, slice-05 page size): Previous/Next
  buttons with an "X–Y of N" window, disabled at both boundaries,
  "End of results." on the last page. Works for the default browse (empty
  query) as well as searches, so inventories beyond 50 rows are fully
  reachable — the slice-01 page silently capped at its fetch limit.
- Reset discipline: submitting a new query restarts at page 0; a shop
  switch resets to a fresh page-0 browse, clears the query, and
  aborts/discards in-flight work. An epoch counter plus
  `shouldApplyShopResult` rejects any response superseded by a newer
  search or a shop change.
- Exact SKU presentation with the verified slice-05 semantics:
  `total === 1` AND the normalized query equal to the returned SKU.
  The matching row/card is highlighted and carries an "Exact SKU match"
  badge. The accepted response (`InventoryItemOut`) returns no barcode
  field, so exact matching is SKU-only — verified, never inferred.
  Partial, fuzzy, name, substring, or multi-result matches stay the
  normal table/cards.
- Responsive: desktop and tablet (md+) render the preserved table;
  phones render stacked cards with the same SKU/set/price/stock data.
  Both layouts read from the same state and the inactive one is
  `display:none`, so screen readers see one copy.
- States: loading skeleton, honest empty ("empty result, not a failed
  write", distinct wording for browse vs search), and classified errors
  for session-expired (401), forbidden (403), not-ready (503), network,
  and general failures via `classifyVendorError` + `reportApiError`.
- Shared helpers: the page reuses `lib/pos-find.ts` (slice-05) unchanged
  — `FIND_PAGE_SIZE`, `findPageWindow`, `offsetForPage`,
  `pageAfterReset`, `classifyFindResponse`. No fork, no behaviour change
  to slice-05.
- Read-only by construction: the page only calls `searchInventory` (GET);
  no edits, adjustments, labels, CSV, resticker, intake, checkout, sync,
  or any mutation path.

## Writes remain visibly locked

- Page-level: "Edit stock / print labels" still opens the locked
  `FeatureNotReady` panel, now enumerating the deferred surfaces (stock
  edits, adjustments, QR labels, resticker, CSV imports, intake, Shopify
  sync, notifications, payments, Watch) and stating the screen is
  read-only.
- Shell-level (unchanged): `components/product/product-sidebar.tsx` keeps
  Sell/Pulls/Stats, Intake/Staging/Resticker/Paperweight, Shopify
  Sync/Review, CSV Import, Reconciliation, and Settings locked with
  "Not ready" markers and the locked-route gates stay in place.

## Preserved and untouched

- Membership authority chain `app/admin/layout.tsx`: VendorShopProvider →
  ProductShell → AdminBillingGate → AdminApiAuthGate → ShopAccessGate.
  Explicit sign-out and shop selector unchanged.
- Inventory visual language: gunmetal surfaces, neon accents, mono
  metadata, `font-display` headings, min-h-11 tap targets, aria-live
  announcements, `role="alert"`/`role="status"` semantics.
- `lib/pos-find.ts`, `app/pos/find/page.tsx`, slice-05 tests, and all
  other slices' accepted code are unmodified.

## Evidence

- `scripts/test_admin_inventory_browse.mjs` (`npm run test:slice06`,
  16 tests): helper reuse, contract totals, pagination math/boundaries,
  reset + stale-response rejection, SKU-only exact semantics with
  barcode-negative cases, responsive layouts, state coverage, membership
  shell wiring, read-only guarantees. Fixtures are clearly labeled
  synthetic data.
- Full frontend suites (slices 01–06, api-auth, landing billing),
  `tsc --noEmit`, and `next build` all passed locally at the final state.
- Responsive/accessibility evidence is code-level (breakpoints, labelled
  controls, live regions, duplicated-layout `display:none`); authenticated
  live smoke remains a staging step, never seed data.
- No backend code, seed data, partner code, barcode inference, writes,
  deployment, migration, or cloud contact in this slice. Barcode PNGs
  remain preserved and untracked.
