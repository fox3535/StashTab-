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

- Clerk signs the user in.
- Protected app routes use Clerk middleware.
- FastAPI calls send `Authorization: Bearer <token>`.
- `X-Shop-Id` is a hint only. Membership on the server is identity.
- Do not send `X-Clerk-User-Id` as identity.
- Session expiry: 401 → sign-in. 403 → no access / wrong shop. 409 →
  conflict. 503 `FEATURE_NOT_READY` → explicit disabled/preview state.

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
  search results, 403 cross-shop, 503 feature-not-ready.
- Responsive checks at desktop and a phone viewport.
- No Convex. No secret leakage in client bundles.
