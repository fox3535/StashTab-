# Independent reviews — fail-closed-shop-identity-v1

**Date:** 2026-08-20  
**Kind:** Architecture, application-security, data-integrity, adversarial
authorization. Then one invite-role correction and one bounded
verification.

## First pass

All four reviewers: **no P0/P1**.

## Slice-local correction

Invite `role` must be `owner` or `staff` (400 otherwise). Test added.

## Residual follow-ups (not blocking this slice)

- Production unique index apply for `(shop_id, clerk_user_id)` on
  existing databases (identity owner; required before production schema
  apply). Model uniqueness and fail-closed duplicate reads are in this
  slice.
- Unused `resolve_clerk_user_id` helper.
- Multi-shop UI picker (API already requires a hint when the user has
  more than one shop).
