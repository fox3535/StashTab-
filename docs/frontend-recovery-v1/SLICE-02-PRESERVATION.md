# Slice-02 dashboard and deferred-route cleanup — preservation record

**Slice:** `frontend-recovery-v1 / slice-02-dashboard-and-deferred-route-cleanup`  
**Base:** `main` `addd8f4`  
**Decisions:** D-039 acceptance; named routine frontend unlock.

## Recovered

- `/admin/dashboard` is an authenticated vendor home inside the accepted
  membership shell (`VendorShopProvider` → `AdminBillingGate` →
  `AdminApiAuthGate` → `ShopAccessGate` from `app/admin/layout.tsx`).
- Shop context comes only from `useVendorShop()` (memberships authority).
  No `NEXT_PUBLIC_DEV_SHOP_ID`, no env shop hint, no invented metrics:
  no revenue, inventory totals, alerts, or operational numbers render.
- Ready cards link to read-only inventory and POS Find. Deferred cards
  (intake, POS checkout, Shopify, notifications, payments, Watch) show
  honest "Not ready" explanations, matching slice-01 lock language.
- Owner styling preserved: `font-display`, neon/gunmetal/steel palette,
  mono uppercase group labels from `product-sidebar.tsx`.

## Deferred-route cleanup

- Bare `/admin/shopify` now renders an authenticated `FeatureNotReady`
  page instead of a 404. The `LockedRouteGate` prefix `/admin/shopify`
  was split into `/admin/shopify/sync` and `/admin/shopify/review` so the
  bare page renders while functional subroutes stay gate-locked.
- `/admin/dashboard` was removed from `LOCKED_PREFIXES` and from the
  sidebar `locked` flag; all other locked routes are unchanged.

## Removed dead code (documented)

- `lib/use-api-auth.ts`: exported `useApiAuth` had zero importers in
  runtime code. It read `NEXT_PUBLIC_DEV_SHOP_ID` as a shop hint, which
  conflicts with the memberships-authority rule (D-038). Removed rather
  than left as a dormant shop-authority source. Doc mentions are
  historical references only.
- Old dashboard KPI fetch (`GET /admin/dashboard` via `adminRequest`)
  removed with the page rewrite. The backend endpoint is untouched; only
  the frontend caller went away. `adminRequest` remains in use by other
  deferred pages.

## Untouched

- Backend, providers, billing, notifications, Shopify logic, writes,
  deployment, and cloud configuration. No Convex. Barcode PNGs and
  `.env.local` excluded.
