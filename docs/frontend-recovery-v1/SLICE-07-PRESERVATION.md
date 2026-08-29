# Slice-07 POS item detail — preservation record

**Slice:** `frontend-recovery-v1 / slice-07-pos-item-detail`
**Base:** `main` `f5e721e`
**Contract:** accepted authenticated `GET /api/v1/inventory/{sku}`
(`services/api/app/routers/inventory.py` `get_by_sku`, response
`InventoryItemOut`): shop-scoped uppercase SKU lookup via verified Clerk
bearer + membership (`get_shop_context`, `X-Shop-Id` is an untrusted
hint), 404 when the item is not listed for the selected shop. No backend
change; the endpoint and the unused frontend wrapper
(`mimirApi.getInventoryBySku`) already existed.

## What was added

- One shared read-only detail experience,
  `components/vendor/vendor-item-detail.tsx`, usable from POS Find and
  admin inventory. Pure helpers in `lib/item-detail.ts`:
  `normalizeDetailSku` (mirrors the server's `sku.upper()` comparison)
  and `shouldApplyDetailResult` (epoch + shop guard).
- Entry is always from the actual SKU returned by the accepted search
  contract ("Details" button per result card / row, labelled
  `View details for SKU …`). The API returns no barcode field, so detail
  identity is SKU-only — never inferred.
- Only contract-backed fields render: name, SKU, sell price
  (`itemSellPrice` sticker/price rule), stock, set, number, game, type,
  variant, condition, sticker price when it differs, and the page's own
  card thumbnail. `InventoryItemOut` has no `location` or `barcode`
  field; nothing about those is shown or invented. Cost and sync_status
  are deliberately not displayed (booth-facing margin and deferred
  Shopify internals).
- States: loading, honest 404 ("SKU X is not listed for <shop>."),
  session-expired, forbidden, feature-not-ready, network, general — all
  via the accepted `classifyVendorError` taxonomy plus `reportApiError`.
- Stale-response protection: epoch counter + `shouldApplyDetailResult` +
  AbortController; a SKU change or shop switch clears the previous record
  and discards late responses. Both pages clear an open detail on
  query/shop reset.
- Accessible Back navigation (labelled Back button, focused on open,
  min-h-12 on POS Find, min-h-11 on admin inventory) and keyboard/mobile
  behaviour preserved.

## Read-only by construction

No sell, reserve, edit, adjust, intake, Shopify, notification, payment,
or Watch action exists in the touched code. The panel states "Read-only
record … Selling, edits, labels, and adjustments are not ready." Admin
inventory keeps its existing "Edit stock / print labels"
FeatureNotReady hint, hidden while a detail is open.

## Preserved and untouched

- Membership authority, Clerk bearer auth, selected-shop hint behaviour,
  and the slice-05/slice-06 search + pagination behaviour (all prior
  suites still pass; 12 new slice-07 tests).
- No backend, schema, API contract, cloud configuration, env file, or
  frozen document changed. Barcode PNG artifacts remain untracked and
  unused; no seed data. Test fixtures are clearly labeled synthetic
  data; staging may only prove the honest empty state.
