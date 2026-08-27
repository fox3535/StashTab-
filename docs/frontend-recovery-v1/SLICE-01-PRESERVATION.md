# Slice-01 preservation notes (local, uncommitted)

Kept:

- Product shell, header, sidebar, dark vendor styling
- Clerk middleware protecting `/admin`, `/pos`, `/dashboard`, `/onboarding`
- `buildProtectedApiHeaders` bearer-token contract
- Landing/marketing routes remain public
- POS Find layout density and inventory table visual language

Adapted:

- Inventory admin page: search-only against `GET /api/v1/inventory/search`
- POS Find: membership shop instead of `NEXT_PUBLIC_DEV_SHOP_ID`
- POS/admin layouts: membership provider + shop gate
- POS More: sign-out and locked settings instead of live-looking Shopify/sales

Deferred in place (URL also blocked by `LockedRouteGate`):

- POS sell/checkout, intake commit, resticker, CSV, Shopify, notifications, payments, Watch

Not copied:

- Convex notification frontend
- Partner Python UI

Deferred preservation-aware cleanup (not this slice):

- `DeferredSellWorkbench` in `app/pos/page.tsx` is unreachable dead code kept
  behind the `FeatureNotReady` return. It preserves the pre-recovery sell
  workbench for the later write slice. Remove or revive it only in a named
  write-enablement slice; do not delete it as routine cleanup.
