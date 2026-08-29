# Slice-09 recent trade history — preservation record

**Slice:** `frontend-recovery-v1 / slice-09-recent-trade-history`
**Base:** `main` `9e3d0f5`
**Status:** draft PR, not merged, not deployed.
**Contract:** accepted authenticated `GET /api/v1/reports/trade-history`
(`services/api/app/routers/reports.py` `trade_history`): shop-scoped via
verified Clerk bearer + membership (`get_shop_context`, `X-Shop-Id` is an
untrusted hint), genuinely trade-typed rows (`transaction_type ==
"trade"` filter, never inferred), newest-first by timestamp, FIXED cap of
200 records, and no pagination, offset, or total. Pure read query; safe
against the current empty staging `sale` table (honest empty result). No
backend change; the endpoint already existed. The legacy CSV export
endpoint is never called by the frontend.

## What was added

- Read-only Recent Trade History screen replacing the legacy
  `app/admin/reports/page.tsx` stub (which used the legacy `adminRequest`
  path and a CSV export button). The legacy export behavior is
  deliberately not revived.
- Pure helpers in `lib/trade-history.ts`: `TRADE_HISTORY_CAP` (200),
  `formatTradeTimestamp`, `formatTradeMoney`, and `cappedTradeNotice`.
  Missing or unparseable values render as an honest "—", never a
  fabricated date or amount.
- Client wrapper `mimirApi.recentTrades` + `TradeRecord` type in
  `lib/mimir-api.ts`, hitting `/reports/trade-history` read-only.
- Honest dashboard entry card ("Recent Trades", states the 200-record
  window) and a labeled sidebar entry for desktop/mobile.
- Only returned fields render: ID, item name, SKU, sold price, trade-in
  value, and timestamp. No totals, profit, margin, customer, payment,
  tax, or inventory data is invented; nothing else is shown.
- The screen states the real contract limits: "up to the newest 200
  records" and "does not paginate". A capped-results notice explains the
  window whenever rows are shown, and explicitly says older trades may
  exist when the response reaches the 200 cap.
- States: loading, honest empty ("No trade transactions are recorded for
  this shop yet. This is an empty result, not a failed write."),
  session-expired, forbidden, feature-not-ready, network, general — all
  via the accepted `classifyVendorError` taxonomy plus `reportApiError`.
- Stale-response protection: epoch counter + `shouldApplyShopResult` +
  AbortController; a shop switch clears the previous shop's trades
  immediately and rejects late responses.
- Live status (`role="status"`) and polite live region; mobile card
  layout with no horizontal overflow. No pagination components were
  forced onto the non-paginated contract.

## Read-only by construction

No trade creation, sale, checkout, refund, export, inventory mutation,
Shopify, notification, payment, or Watch behaviour exists in the touched
code. All remaining locked routes (intake, staging, resticker,
paperweight, Shopify, imports, reconciliation) stay locked.

## Preserved and untouched

- Membership authority, Clerk bearer auth, selected-shop hint behaviour,
  and every prior slice's behaviour (all prior suites still pass; 12 new
  slice-09 tests; the vendor-core dashboard-link tests were extended to
  expect the fourth honest tool link).
- No backend, schema, API contract, cloud configuration, env file, or
  frozen document changed. Barcode PNG artifacts remain untracked and
  unused; no seed data. Test fixtures are clearly labeled synthetic
  data; staging may only prove the honest empty state.
