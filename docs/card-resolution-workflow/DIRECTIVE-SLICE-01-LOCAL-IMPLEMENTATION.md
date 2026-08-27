# Prepared directive — slice-01 local intake/abstention (NOT AUTHORIZED)

**Status:** `PREPARED — DO NOT EXECUTE`  
**Frozen policy:** `identity-score-v0`  
**Contract:** `STASHTAB-CARD-RESOLUTION-001` v1.0.0  
**This document is not an implementation unlock.**

When a later named unlock is given, the smallest first code slice is:

1. Authenticated, shop-scoped intake endpoint in FastAPI (JWT + membership;
   `X-Shop-Id` is a hint only).
2. Apply `identity-score-v0` only. Integer hundredths. Auto-accept only at
   100 with six exact fields, one eligible identity, margin ≥ 10.
3. Outcomes: accept (identity only), abstain (durable shop-scoped review
   row), or reject. No inventory, lot, event, price, sale, purchase,
   Shopify, payment, Watch, or notification writes.
4. JustTCG and TCGCSV remain off. No provider HTTP. RapidFuzz retrieve
   only, never verify.
5. Tests against **disposable local PostgreSQL** only. No staging Neon
   DDL. Replay same `intake_id` is idempotent.

Stop after tests pass. Do not commit, push, deploy, or migrate unless
that later unlock explicitly allows it.
