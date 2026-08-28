# F1 vendor-core recovery batch — preservation record

**Batch:** `feature/f1-vendor-core-recovery-batch` (unattended F1 vendor-core
authorization, 2026-08-28)
**Base:** `main` `aaac4e4` (merge commit of PR #23 / slice-06)
**Scope:** public landing, `/onboarding`, authenticated vendor shell,
`/admin/dashboard`, `/admin/inventory`, `/pos/find`. Frontend only — no
backend, schema, staging writes, deployment, or cloud contact.

## A. Onboarding recovery

`app/onboarding/page.tsx` was rewritten as a memberships-first flow using
only accepted FastAPI contracts:

- Loads `GET /shops/me/memberships` with the Clerk bearer only
  (`omitShopHeader: true`). No `X-Clerk-User-Id`, no `clerk_user_id`, no
  dev-shop fallback, no Shopify credentials collected.
- One or more memberships → straight to `/admin/dashboard` ("Opening your
  dashboard…" status). Zero memberships → accessible vendor-shop setup
  form with only the API-supported fields `name` + `slug` (`POST /shops`).
- States: loading, session-expired, memberships error with Retry + sign
  out, validation errors, duplicate-slug 409 with a fixable message
  ("That URL slug is already taken. Choose a different slug and try
  again."), network/general failures. Double submission is guarded by
  state plus a ref.
- Success refreshes memberships best-effort, stores only the validated
  shop preference (`writeShopPreference(shop.id)`), then enters the
  dashboard. Shopify/payments/notifications are stated as deferred on the
  form itself.
- Pure helpers live in `lib/onboarding.ts`: `normalizeShopSlug`,
  `suggestSlug`, `validateShopSetup`, `decideOnboardingScreen`,
  `messageForCreateFailure`. Submission uses the displayed suggested slug
  (`effectiveSlug`), so a name-only entry works.

## B. Vendor-core consolidation

`components/vendor/vendor-patterns.tsx` extracts only behaviour already
duplicated by at least two accepted pages: `PageHeader` (dashboard,
inventory, find), `VendorStatePanel` (shop-access gate + onboarding),
`VendorErrorBanner` and `VendorLoadingBlock` (inventory + find),
`BrowsePagination` (inventory + find, windows still come from the
slice-05 `findPageWindow`). Classes and strings are the same ones the
pages already rendered; slice-05/06 assertions were re-pointed at the
patterns file and stay green. Sign-out clears shop-sensitive state
(`clearLocalSession` → preference + selection + phase); shop switches
already reset page state via the preserved epoch/abort logic.

## C. Regression coverage

`scripts/test_vendor_core_batch.mjs` (`npm run test:vendor-core`,
16 tests): public vs protected routing, onboarding redirect/create states,
API-supported-field validation, duplicate-slug handling, sign-out
clearing, dashboard honest cards (only `/admin/inventory` + `/pos/find`
linked; deferred cards never linked; "never invents numbers"), all common
error messages, deferred-feature honesty, accessible/mobile markup, and
negative checks (no Convex/Svix, no user-ID header, no dev-shop
authority, no fixture data in runtime code, billing widget confined to
landing + billing gate). Memberships/stale-preference/exact-SKU/
pagination/stale-rejection coverage stays in the earlier suites.

## Evidence

- Review: one bounded architecture/UX/a11y/security/preservation review.
  Findings corrected in the same batch: submit the displayed suggested
  slug (P0 happy-path validation failure) and restore the accepted
  POS Find loading-block markup.
- All frontend suites (api-auth, slice-01..06, landing billing,
  vendor-core), `tsc --noEmit`, and `next build` passed at the final
  state. Secret/artifact/whitespace scans clean; barcode PNGs remain
  preserved and untracked.
- No frozen contract was edited. Writes remain visibly locked; no locked
  feature appears operational.
