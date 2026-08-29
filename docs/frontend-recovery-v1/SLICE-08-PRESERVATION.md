# Slice-08 sales history browse — preservation record

**Slice:** `frontend-recovery-v1 / slice-08-sales-history-browse`
**Base:** `main` `3dfe7fb`
**Status:** draft PR, not merged, not deployed.
**Contract:** accepted authenticated `GET /api/v1/sales/history`
(`services/api/app/routers/sales.py` `sales_history`, response
`SalesHistoryResponse { sales: SaleOut[], total: int }`): shop-scoped
records via verified Clerk bearer + membership (`get_shop_context`,
`X-Shop-Id` is an untrusted hint), newest-first, `limit` clamped 1–200
plus `offset` and an honest record-count `total`. The `/history` route is
declared before any `{sale_id}` route, so there is no route-ordering
hazard. Pure read query; safe against the current empty staging `sale`
table (honest empty result). No backend change; the endpoint already
existed and the client wrapper `mimirApi.salesHistory` gained `offset`
support only.

## What was added

- Read-only Sales History screen `app/admin/sales/page.tsx` inside the
  authenticated vendor shell, plus an honest dashboard entry card and a
  "Sales History" sidebar entry (desktop and mobile share the sidebar
  pattern).
- Pure helpers in `lib/sales-history.ts`: `SALES_PAGE_SIZE`,
  `formatSaleTimestamp`, and `formatSaleMoney`. Missing or unparseable
  values render as an honest "—", never a fabricated date or amount.
- Pagination uses the contract's `limit`, `offset`, and `total` through
  the shared `offsetForPage` / `findPageWindow` / `pageAfterReset`
  helpers and the shared `BrowsePagination` control, including
  end-of-results behaviour from the shared window info.
- Only `SaleOut` fields render: item name, SKU, game, transaction type,
  sold price, and timestamp. `profit`, `trade_in_value`, and
  `net_revenue` are deliberately not displayed (booth-facing margin and
  internals); nothing else is shown or invented.
- States: loading, honest empty ("No sales are recorded for this shop
  yet. This is an empty result, not a failed write."), session-expired,
  forbidden, feature-not-ready, network, general — all via the accepted
  `classifyVendorError` taxonomy plus `reportApiError`.
- Stale-response protection: epoch counter + `shouldApplyShopResult` +
  AbortController; a shop switch clears the previous shop's sales
  immediately and rejects late responses.
- Live status (`role="status"`) and polite live region; keyboard-
  accessible named controls; mobile card layout with no horizontal
  overflow.

## Read-only by construction

No sale creation, checkout, refund, cancellation, inventory mutation,
Shopify, notification, payment, or Watch behaviour exists in the touched
code. No revenue metrics, trends, charts, exports, or inferred
customer/payment details. The page states "Read-only; refunds, exports,
and metrics are not ready." Direct locked routes remain locked.

## Preserved and untouched

- Membership authority, Clerk bearer auth, selected-shop hint behaviour,
  and every prior slice's behaviour (all prior suites still pass; 11 new
  slice-08 tests; the vendor-core dashboard-link test was extended to
  expect the third honest tool link).
- No backend, schema, API contract, cloud configuration, env file, or
  frozen document changed. Barcode PNG artifacts remain untracked and
  unused; no seed data. Test fixtures are clearly labeled synthetic
  data; staging may only prove the honest empty state.
