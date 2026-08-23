# fail-closed-shop-identity-v1 — acceptance

**Decision:** APPROVED (human owner)  
**Date:** 2026-08-23  
**Status:** `COMPLETED`

## Acceptance evidence

| # | Requirement | Evidence |
|---|---|---|
| 1 | Exact issuer validation | `jwt.decode(issuer=...)` bound to configured Clerk issuer; negative `test_wrong_issuer_rejected`. |
| 2 | Clerk authorized-party binding (`azp`) | `CLERK_AUTHORIZED_PARTIES` allowlist enforced post-decode; negative `test_wrong_azp_rejected`. |
| 3 | Optional configured audience validation | `aud` verified when `CLERK_JWT_AUDIENCE` set; fail-closed when absent on production-like envs. |
| 4 | Expiry and `nbf` validation | `verify_exp` / `verify_nbf` on; `exp` required. Negatives: `test_expired_token_rejected`, `test_future_nbf_rejected`. |
| 5 | JWKS key rotation by `kid` | `PyJWKClient` resolves signing key per `kid`; rotation keeps issuer+azp checks (`test_key_rotation_keeps_issuer_and_azp`). |
| 6 | Verified-token user identity | User id only from token `sub`; headers never authenticate (`test_header_only_user_rejected_in_production`). |
| 7 | Membership enforcement | `require_membership` after token verification; wrong/no shop forbidden (HTTP negatives). |
| 8 | Fail-closed environment configuration | Missing issuer or azp/aud config fails closed on staging/production/invalid `APP_ENV` (three negatives). |
| 9 | Duplicate-membership rejection | Unique `(shop_id, clerk_user_id)` on model; read-time 403 on duplicates; insert test passes. |
| 10 | Test suite | 70 passing tests at check time (`pytest` full API suite). |

Details in `reviews/JWT-CHECK.md`.

## Recorded deployment gate

`DEPLOYMENT GATE — IDENTITY OWNER — REQUIRED BEFORE PRODUCTION SCHEMA APPLY`

Add the unique `(shop_id, clerk_user_id)` index to already-created
production databases as a controlled schema step. This does **not** block
isolated development, but production preparation may not silently omit it.

## Consequence

The `inventory-truth-v1` entry gate is satisfied. A separate named human
unlock approved `inventory-truth-v1 / slice-01-receive-foundation`.
