# Bounded review — intake/abstention planning packet

**Target:** `PLAN-SLICE-01-INTAKE-ABSTENTION.md`  
**Pin:** `d49eca9fc31298847bd07abf42347ab691b4f974`  
**Lenses:** architecture, data integrity, application security, adversarial/concurrency, AI-evaluation quality, workflow liveness  
**Budget:** one review, one correction, one verification. No further loop.

## Findings

| Lens | Finding | Severity |
|---|---|---|
| Architecture | Durable review cannot live only in memory. Previous “no schema” line conflicted with durability. Local PG tables, not staging Neon, is the smallest fix. | P1 — corrected |
| Architecture | Existing `/admin/intake/*` is Pokemon lookup + staging write, not this workflow. Keeping it unused is required. | OK |
| Data integrity | `accepted` must not imply §10 inventory commit. Price confidence stays null. Unique `(shop_id, intake_id)` required. | OK after stating identity-only accept |
| Data integrity | Contract §13.2–3 (JustTCG cache/spend) cannot pass in this slice. They must stay explicit remaining gates, not fake-pass. | P1 — corrected |
| Application security | `/admin/intake/lookup` is unauthenticated today. New routes must use JWT + membership. Lookup must not be reused. | OK |
| Adversarial / concurrency | Unique key + return existing row. Cross-shop candidate lists fail closed. Advisory agents cannot accept. | OK |
| AI-evaluation quality | Fuzzy partner `>= 80` and promo “best card” would auto-identify. This slice forbids fuzzy-only auto-accept. Labeled-set gate (§13.14) remains later. | OK |
| Liveness | Abstain is a counted terminal for this slice. Human decide is optional completion, not required to close the request. Timeouts are not success. | OK |

## Correction applied

1. Proposed four resolution tables on **local** Postgres; staging Neon apply remains a later unlock.
2. Contract §13 JustTCG/inventory items listed as **remaining**, not slice pass criteria.
3. Human `accept_identity` still cannot write inventory.
4. Unauthenticated Pokemon lookup called out as do-not-reuse.

## Verification

Packet states: three outcomes; JustTCG never called; no inventory mutation;
shop-scoped durable review; idempotent replay; no contract amendment unless
thresholds or auto-accept-without-lookup change. Implementation remains locked.
