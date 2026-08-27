# Frontend architecture — recovery target

Pinned `main`: `6a266b10639df2931e1bd37d4040b49a0efd0bd2`.

## Runtime shape

```text
Browser
  → Next.js (Clerk session, layout, routing)
      → FastAPI (Bearer token + membership)
          → Neon PostgreSQL
```

Convex is forbidden. The browser must not talk to Neon.

## Identity and shop context

Owner decisions (2026-08-27): FastAPI membership is shop authority. A
stored/local shop ID is only a preference and must match current
memberships. One membership auto-selects. Several memberships show a
selector. Stale preference is discarded. No caller-supplied user
headers. No silent development shop fallback.

- Clerk signs the user in. Explicit sign-out is required in desktop
  shell and mobile nav.
- Protected app routes use Clerk middleware. Landing stays public.
- FastAPI calls send `Authorization: Bearer <token>`.
- `X-Shop-Id` is a hint only, and only after membership validation.
- Do not send `X-Clerk-User-Id` as identity.
- Session expiry: 401 → sign-in. 403 → no access / wrong shop. 409 →
  shop selection required. 503 `FEATURE_NOT_READY` → explicit disabled
  state with explanation, never fake success.

## Application shells

1. Public marketing: `app/(marketing)/`.
2. Authenticated vendor app: one shell with navigation, shop chip,
   sign-out, loading, empty, error, and feature-not-ready banners.
3. Show-floor POS: same auth and API rules, denser layout, larger tap
   targets. Checkout stays preview/disabled until write unlock.

## Data access

- Shared fetch helper: bearer + optional shop hint, typed errors for
  401/403/409/503.
- Read-ready now: shop membership, inventory search/read.
- Write-disabled: inventory PATCH, checkout, intake commit, CSV quantity,
  Shopify sync, card-resolution (flag off).
- Deferred/missing: notification preferences UI, Watch, payments capture.

## UX rules

- Unavailable features look locked, not operational.
- Empty inventory is a valid success state (D-029).
- Desktop, tablet, and phone layouts from the first implementation slice.
- Preserve barcode/label and resticker intent; do not enable those writes
  in slice-01.

## Testing

- Auth header contract tests (already present).
- Screen tests: signed-out redirect, session expired, empty inventory,
  search results, 403 cross-shop, 409 shop selection, 503
  feature-not-ready, zero memberships, stale shop preference discarded.
- Responsive checks at desktop, tablet, and phone viewports.
- No Convex. No secret leakage in client bundles.
