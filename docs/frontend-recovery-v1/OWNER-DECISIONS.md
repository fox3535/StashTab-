# Owner decisions — frontend recovery slice-01

Recorded 2026-08-27. These decisions unlock **planning and later named
implementation** of slice-01. They do not start code in this docs PR.

1. Approve first frontend slice:
   `frontend-recovery-v1 / slice-01-authenticated-shell-and-readonly-inventory`.
2. Verified FastAPI shop membership is the authority for shop context.
3. A stored or local shop ID is only a selection preference. It cannot
   grant access and must be checked against current memberships.
4. If the user has exactly one membership, select it automatically.
5. If the user has multiple memberships, show an authorized shop selector.
6. If the stored preference is stale or unauthorized, discard it and
   require a valid selection.
7. Never use caller-supplied user headers or a silent development shop
   fallback.
8. Add explicit sign-out in the authenticated desktop shell and mobile
   navigation.
9. Keep landing and public marketing pages public.
10. Keep these deferred and visibly disabled, with a not-ready explanation
    (never silent no-op, never fake success):
    - Shopify connection/sync
    - POS checkout/selling
    - intake commit
    - resticker writes
    - CSV quantity writes
    - notification settings and service worker
    - payments and Watch
11. Read-only inventory search is the first real backend-backed screen.
12. Disabled actions must explain that the feature is not ready.
