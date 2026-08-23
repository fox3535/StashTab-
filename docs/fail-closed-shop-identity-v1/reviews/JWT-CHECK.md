# JWT acceptance check — fail-closed-shop-identity-v1

**Date:** 2026-08-23  
**Kind:** bounded JWT check only. Not a new general review cycle.  
**Status:** corrections applied; slice still awaiting human acceptance.

## Checks

| # | Rule | Result |
|---|---|---|
| 1 | Signature via Clerk JWKS | Pass — `decode_bearer_user_id` uses `PyJWKClient` at `{issuer}/.well-known/jwks.json` and `jwt.decode(..., algorithms=["RS256"])`. Negative: `test_wrong_signature_rejected`. |
| 2 | Exact issuer | Pass — `issuer=` is the configured Clerk issuer. Negative: `test_wrong_issuer_rejected`. |
| 3 | `exp` / `nbf` | Pass — `verify_exp` and `verify_nbf` are on; `exp` is required. Negatives: `test_expired_token_rejected`, `test_future_nbf_rejected`. |
| 4 | Application binding | Pass — Clerk `azp` allowlist (`CLERK_AUTHORIZED_PARTIES`); optional `aud` if `CLERK_JWT_AUDIENCE` is set. Negative: `test_wrong_azp_rejected`. |
| 5 | User from verified token only | Pass — decoder does not read user headers. HTTP: `test_header_only_user_rejected_in_production`. |
| 6 | Membership after token | Pass — `require_membership` after `decode_bearer_user_id`. HTTP: `test_jwt_without_membership_forbidden`, `test_jwt_wrong_shop_forbidden`. |
| 7 | Missing/invalid issuer or azp/aud config in staging/production | Pass — empty issuer, empty azp+aud on staging/production/invalid env fail closed. Tests: `test_missing_issuer_config_production_rejected`, `test_missing_azp_config_staging_rejected`, `test_invalid_env_missing_azp_config_rejected`. |
| 8 | Key rotation without dropping issuer/azp | Pass — JWKS lookup by `kid`; rotated keys still require issuer+azp. `test_key_rotation_keeps_issuer_and_azp`. |

## Membership duplicates

Duplicate `(shop_id, clerk_user_id)` **could** change role via `.first()`. This slice now:

- unique constraint on the model
- `require_membership` returns 403 if more than one row is read
- insert test `test_duplicate_membership_insert_rejected`

**Follow-up (identity owner, before production schema apply):** add the same unique index on already-created production databases. Not an inventory-truth migration.

## Tests

`pytest tests/test_jwt.py tests/test_identity.py tests/test_notifications.py tests/test_logic.py` — 70 passed.

## Recommendation

Accept the identity slice after this JWT correction. Do not mark `completed` until a human accepts. Inventory-truth stays blocked.
