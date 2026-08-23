# IMPLEMENTATION DIRECTIVE (PREPARED — NOT EXECUTED) — slice-02-outbound-events

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.1.0 (AMENDMENT-1.1.0 applied)
**Directive status:** `AWAITING NAMED HUMAN IMPLEMENTATION APPROVAL`
**Prepared:** 2026-08-23 · Plan source: `DIRECTIVE-SLICE-02.md` v3 (frozen)

## Authorized scope (implementation only when unlocked)

1. **Schema (migrator-only):** extend `TRUTH_TABLE_NAMES` with
   `inventory_channel_observation`, `refund_record`, `return_record`,
   `inventory_exception` per AMENDMENT-1.1.0 envelope; composite FKs;
   `uq_obs_shop_channel_ref`; append-only DB enforcement for refund/
   return tables; create_all-prevention gate test extended.
2. **POS/show outbound:** one `sell_sale:{shop}:{sale_id}` event per line
   in the Sale transaction; observation row same transaction; populated
   `sale_id`; insufficient stock → `409 Conflict` with stable code, zero
   partial mutation.
3. **Shopify pull outbound:** `sell_shopify_order_line:…` events;
   over-sale → −S event + single reused exception + vendor alert
   (in-app critical; Web Push only behind existing gates and opt-in);
   auto-pause untouched; per-line failed_permanent containment.
4. **Observation ledger arbitration:** insert-or-get within the truth-pair
   transaction; loser rolls back before any snapshot write; duplicate-
   suspicion detection in reconcile output.
5. **Refund/return model (records only):** append-only tables; confirmed
   whole-unit resalable returns write one positive event atomically with
   actor/shop/timestamp/original-ref/qty/outcome captured; no payment
   execution of any kind.
6. **Reconciliation extension:** per-type breakdown, open-exception list,
   duplicate-suspicion surfacing.
7. **Tests:** the twelve TESTS.md slice-02 tests incl. PG harness extension
   in the blocking CI job.

## Explicitly outside this unlock

Adjustment/PATCH/CSV unfreeze; production cutover; refund payment flows;
manual-resolution UI (workflow authorization is a separate pre-cutover
gate); payments; Watch; SMS; retention-policy automation.

## Acceptance process when unlocked

Implementation → twelve acceptance tests green → PG harness ×2 fresh DBs →
SQLite suite green with slice-01 tests unchanged → five independent
reviews (Architecture, Data-integrity, Database-security,
Adversarial/concurrency, Workflow-liveness) → one bounded correction pass
→ one bounded verification → stop for human acceptance decision.

## Standing gates after acceptance

Manual-resolution workflow + adjust slice complete + zero mismatches +
zero open critical exceptions before any production outbound cutover.
No commit/push/deploy/migrations without explicit approval.
