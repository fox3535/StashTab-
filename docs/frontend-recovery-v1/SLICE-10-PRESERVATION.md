# Slice-10 price update review — preservation record

**Slice:** `frontend-recovery-v1 / slice-10-price-update-review`
**Base:** `main` `c7e05aa`
**Status:** draft PR, not merged, not deployed.
**Contract:** accepted authenticated `GET /api/v1/admin/inventory/updated`
(`services/api/app/routers/admin.py` `list_updated_cards`): shop-scoped via
verified Clerk bearer + membership (`get_shop_context`, `X-Shop-Id` is an
untrusted hint), filters `InventoryItem.shop_id == ctx.shop_id` AND
`needs_update IS TRUE`, ordered by name. Pure read query: it performs no
mutation. It returns `id`, `sku`, `name`, `old_price`, `price`, and
`shop_listing_price` only. The route has NO cap and NO pagination: it
returns the full current set in one response, so no completeness guarantee
exists beyond the current response. Every column selected or filtered
(`needs_update`, `old_price`, `price`, `shop_listing_price`) exists in the
approved staging `inventory_item` schema
(`inventory_live_schema/migrator.py`), and the API role holds SELECT only
on that table. Empty table yields an honest empty `items` list. The write
halves of the pricing workflow (approve, approve-all, revert) are never
called.

## What was added

- Read-only Price Updates screen at `app/admin/price-updates/page.tsx`.
  It explains that it shows inventory records carrying a pending/previous
  price update as defined by the API (records the API flagged
  `needs_update == true`).
- Pure helpers in `lib/price-updates.ts`: `PRICE_UPDATES_LARGE_THRESHOLD`
  (200, a UI hint only), `formatPriceUpdateMoney`, and
  `priceUpdateSetNotice`. Missing optional values render as an honest
  "—", never a fabricated amount.
- Client wrapper `mimirApi.priceUpdates` + `PendingPriceUpdate` type in
  `lib/mimir-api.ts`, hitting `/admin/inventory/updated` read-only.
- Honest dashboard entry card ("Price Updates", states approving and
  repricing are not ready) and a labeled sidebar entry for
  desktop/mobile.
- Only returned fields render: name, SKU, old price, current price, and
  shop listing price. No margin, market price, provider price, profit,
  recommended action, or completion status is inferred; nothing else is
  shown.
- The screen documents the real API limitation: the notice states the
  endpoint has no cap and no pagination and returns the current set in
  one response, and adds a large-result note at 200+ rows. No pagination
  or completeness is claimed.
- States: loading, honest empty ("No inventory records carry a
  pending/previous price update for this shop right now. This is an
  empty result, not a failed write."), session-expired, forbidden,
  feature-not-ready, network, general, and a large-result information
  state — all via the accepted `classifyVendorError` taxonomy plus
  `reportApiError`.
- Stale-response protection: epoch counter + `shouldApplyShopResult` +
  AbortController; a shop switch clears the previous shop's records
  immediately and rejects late responses.
- Live status (`role="status"`) and polite live region; desktop table and
  mobile card layout with no horizontal overflow. No pagination
  components were forced onto the uncapped contract.

## Read-only by construction

No approve, dismiss, edit, reprice, export, inventory mutation, provider
lookup, Shopify, notification, payment, or Watch behaviour exists in the
touched code. Legacy pricing and resticker actions are not revived. All
remaining locked routes (intake, staging, resticker, paperweight,
Shopify, imports, reconciliation) stay locked.

## Preserved and untouched

- Membership authority, Clerk bearer auth, selected-shop hint behaviour,
  and every prior slice's behaviour (all prior suites still pass; 11 new
  slice-10 tests; the vendor-core and slice-09 dashboard-link tests were
  extended to expect the fifth honest tool link).
- No backend, schema, API contract, cloud configuration, env file, or
  frozen document changed. Barcode PNG artifacts remain untracked and
  unused; no seed data. Test fixtures are clearly labeled synthetic
  data; staging may only prove the honest empty state.
