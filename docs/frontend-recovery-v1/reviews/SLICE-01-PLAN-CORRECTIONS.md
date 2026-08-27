# Correction pass — F1 slice-01 plan

One pass. No extra review loop. No frontend code.

1. `GET /api/v1/shops/me` is not a membership list. Selector requires an
   optional read-only memberships GET if existing reads cannot list
   shops. Do not invent shops from env or Clerk metadata.
2. Empty search copy must match D-029: in-stock results only. Empty
   is success, not an error and not a write failure.
3. HTTP map includes 404 no-membership. Zero memberships do not start
   onboarding or shop create in this slice.
4. 403 and 409 discard stale preference; they do not silently pick
   another shop.
5. 503 FEATURE_NOT_READY is for locked/gated features. It is not the
   empty-inventory state.
6. Disabled actions show durable “not ready” copy, not a success
   toast or silent no-op.
7. Tablet is a required layout, not desktop-only plus phone.
8. This packet does not unlock implementation, deploy, writes, or
   production.
