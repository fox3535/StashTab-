# Slice-03 authenticated entrypoint consolidation — preservation record

**Slice:** `frontend-recovery-v1 / slice-03-authenticated-entrypoint-consolidation`  
**Base:** `main` `ee27e7b`  
**Owner decisions:** `/admin/dashboard` is the sole authenticated vendor
dashboard; retire the stale `/admin` KPI page and the starter `/dashboard`
demo page; preserve the public landing; onboarding success enters
`/admin/dashboard`.

## Redirects added (Clerk protection preserved)

- `/admin` → server `redirect("/admin/dashboard")`. Middleware
  `auth.protect()` on `/admin(.*)` is unchanged, so the redirect only
  happens after sign-in and keeps the sign-in return intent.
- `/dashboard` → server `redirect("/admin/dashboard")` with unchanged
  `/dashboard(.*)` protection.

## Retired owner work (prior locations documented)

- Stale `/admin` KPI hub lived at `app/admin/page.tsx`: a link grid of
  ten tools (including deferred intake, Shopify sync/review, CSV import,
  reconciliation, reports) plus a "Back to POS" link into locked `/pos`.
  Navigation continues in `components/product/product-sidebar.tsx` with
  honest Not Ready states, and the vendor home is
  `app/admin/dashboard/page.tsx` (slice-02).
- Starter demo dashboard page lived at `app/dashboard/page.tsx`
  composing `SectionCards`, `ChartAreaInteractive`, and `DataTable` with
  sample `data.json` (no FastAPI binding). The page route now redirects;
  the demo components and `app/dashboard/layout.tsx` /
  `app/dashboard/payment-gated/` remain in the tree untouched for later
  design-system recovery. No files deleted.

## Stale destinations updated

- Onboarding step 2 ("Finish" and "Skip for now") pushed `/pos`, which is
  a locked FeatureNotReady screen. Both now enter `/admin/dashboard`;
  button copy updated to "Finish & open dashboard". The onboard POST and
  Shopify credential PUT logic are unchanged.
- Public landing signed-in CTA "Open POS" linked locked `/pos`. It now
  links `/pos/find` (the live read-only floor tool) as "Open POS Find".
  The landing itself stays public and untouched otherwise; sign-out still
  returns to `/`.

## Untouched

- Middleware matchers, backend, billing, writes, Shopify logic,
  notifications, deployment, and cloud configuration. No Convex.
  Barcode PNGs and `.env.local` excluded.
