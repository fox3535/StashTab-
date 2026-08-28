# Slice-04 stale link and starter route cleanup — preservation record

**Slice:** `frontend-recovery-v1 / slice-04-stale-link-and-starter-route-cleanup`  
**Base:** `main` `038b46b`  
**Closes:** the stale-link / starter-route cleanup track. After this slice no
further one-link honesty slices are expected: every reachable landing link,
retired starter route, and billing-implying demo surface on `main` has been
audited and corrected or preserved below.

## Corrected visible links

- Landing footer `app/(landing)/footer.tsx`: "Open POS" → locked bare
  `/pos` became explicit "Open POS Find" → `/pos/find`, matching the
  slice-03 header rule (a specialized target requires an explicit label).
- Sweep of `app/` and `components/` found no other visible link presenting
  a locked route as operational. Remaining locked-route links live only
  inside pages that are themselves gate-locked and unreachable:
  `app/admin/staging/page.tsx` → `/admin/intake`,
  `app/admin/intake/page.tsx` → `/admin/staging`,
  `app/admin/paperweight/page.tsx` → `/admin/settings`. They render never
  (LockedRouteGate shows FeatureNotReady first) and are preserved in place.

## Retired starter routes under `/dashboard/**`

- `app/dashboard/page.tsx` already redirected to `/admin/dashboard`
  (slice-03).
- `app/dashboard/payment-gated/page.tsx` previously implied working billing:
  Clerk `Protect` plan gating plus a `CustomClerkPricing` upgrade widget
  ("Upgrade to a paid plan"). StashTab has no live billing. It now
  server-redirects to `/admin/dashboard`; middleware `auth.protect()` on
  `/dashboard(.*)` preserves sign-in protection. No files deleted:
  `components/custom-clerk-pricing.tsx` and the demo dashboard chrome
  (`app/dashboard/layout.tsx`, `app-sidebar.tsx`, `site-header.tsx`,
  `nav-main.tsx`, `nav-secondary.tsx`, `nav-documents.tsx`, `nav-user.tsx`,
  `data-table.tsx`, `chart-area-interactive.tsx`, `section-cards.tsx`,
  `loading-bar.tsx`, `data.json`) remain in the tree, unreachable through
  any route, for later design-system recovery.

## Preserved and untouched

- Public landing, Clerk middleware matchers, accepted vendor shell,
  locked-route gate (bare `/pos` stays locked; links were corrected, not
  routes unlocked).
- No backend, billing enablement, payments, Shopify, notifications, writes,
  deployment, or cloud changes. No Convex. Barcode PNGs and `.env.local`
  excluded.
