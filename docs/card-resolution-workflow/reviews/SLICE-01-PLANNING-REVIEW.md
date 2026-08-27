# Bounded planning review — slice-01 intake/abstention

**Target:** `PLAN-SLICE-01-INTAKE-ABSTENTION.md`  
**Pin:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**Pass:** one review, one correction. No implementation.

## Findings

| Lens | Result |
|---|---|
| Architecture | Smallest F0 leftover that does not need staging writes. Keep inventory-truth staging proof queued, not deleted. |
| Partner | Plan cited partner lookup/staging correctly as analog, not copy. Exact names: `process_card`, `fetch_card_data`, `add_to_staging`. Current API is `POST /admin/intake/lookup` and `POST /admin/intake/staging`. |
| DB / security | No staging DDL is correct. Do not reuse `staging_item`. |
| Integrity | Abstain on ambiguity is required. Auto-accept only from caller-supplied local candidates, not network lookup. |
| Tenant | `shop_id` required. Candidates from another shop must fail closed. |
| Adversarial | Do not invoke existing intake routes; they can hit missing tables or write. No JustTCG/Pokemon calls. |
| Ops | Local tests only. No Railway/Neon/Clerk. |
| Liveness | Planning only. |

## Correction applied

See updated partner table, exact current routes, and explicit cross-shop candidate rejection in the plan.
