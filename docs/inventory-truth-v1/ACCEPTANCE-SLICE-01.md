# slice-01-receive-foundation — acceptance record

**Contract:** `STASHTAB-INVENTORY-TRUTH-001` v1.0.0 (frozen)
**Slice:** `slice-01-receive-foundation`
**Decision:** **APPROVED by human owner, 2026-08-23**
**Evidence of record:** `reviews/SLICE-01-PG-ACCEPTANCE.md`
(implementation: `reviews/SLICE-01-IMPLEMENTATION.md`; corrections:
`reviews/IMPLEMENTATION-CORRECTIONS.md`)
**Status:** `COMPLETED — NOT DEPLOYED`

## Accepted evidence

| Item | Result |
| --- | --- |
| 14 PostgreSQL owner criteria | PASS — full harness green twice on fresh disposable databases (synthetic data only; containers destroyed after runs) |
| SQLite regression suite | 104 passed (70 prior + 20 slice + 14 PG-harness) |
| Historical backfill | Actual result recorded (not just intended key behavior): +5 purchase backfill / +3 opening gap / −5 loss / zero-gap no-op; deterministic on re-run |
| Reconciliation | Zero mismatches across all test shops; identical results on immediate re-run |
| Inventory loss (`loss` event) | Created no Sale row (asserted) |
| Migration | Atomic single transaction; mid-point injected failure leaves no partially accepted schema; second run idempotent no-op |
| Freeze failure propagation | Staging commit and trade receive raise instead of silently skipping; POS maps freeze to 503; trade loop re-raises rather than counting errors |
| CI gate | `.github/workflows/inventory-truth-gates.yml` — blocking PR job; ephemeral CI Postgres service container; no repository secrets, no production credentials |

## Corrections accepted as part of this slice

Overlay check-constraint boolean wording (PostgreSQL-valid), atomic migrator
with fail-after test hook, re-call-safe composite FK registration, POS 503
freeze mapping, trade-loop re-raise of freeze/failed-permanent.

## Standing gates carried forward (unchanged)

1. **Human approval before any production schema application** (contract §4
   schema-apply gate; executive sponsor).
2. **Production membership unique index** `(shop_id, clerk_user_id)`
   (`DEPLOYMENT GATE — IDENTITY OWNER — REQUIRED BEFORE PRODUCTION SCHEMA
   APPLY`, per `docs/fail-closed-shop-identity-v1/ACCEPTANCE.md`).
3. **Cutover reconciliation must equal zero** at go-live for every shop;
   timeout is not green.
4. **Cutover operations runbook, audit logging, and break-glass procedure**
   required before production cutover use (DATABASE-CONTROLS §7 alignment;
   documented break-glass path).

## Explicitly not done

No production migration applied, no commit/push/deploy, no production
credentials used. Sell/Shopify outbound dual-write is a later slice needing
a new unlock. Direct stock overwrites (PATCH/CSV) remain frozen until the
adjust slice.
