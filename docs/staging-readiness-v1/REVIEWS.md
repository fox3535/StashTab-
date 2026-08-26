# Independent planning reviews and bounded verification

Reviewers used merge `c3647a4eda37d355ed47f9e77ad667e4fda7930c`. No deploy, migrate, or cloud create.

A broad review loop is **not** restarted. One bounded correction (safeguards + owner decisions) and one final verification follow.

## Original planning findings (closed or deferred as noted)

| ID | Finding | Disposition |
| --- | --- | --- |
| P0 | Dual-write queries missing cutover table → 500 | **Closed in plan:** `503 FEATURE_NOT_READY` (`SAFEGUARDS.md`). Code in slice 0. |
| P0 | Runtime as table owner; migrator `CREATE ROLE` trap | **Closed in plan:** role script + owner execution; runtime env must not set migrator role-create. Proof still required on real Neon before truth apply. |
| P0 | Worker default-on Shopify if settings missing | **Closed in plan:** missing settings/tokens = off. Code in slice 0; worker still not provisioned. |
| P0 | `DEPLOY.md` as staging recipe | **Closed:** outdated; `RUNBOOK.md` is the staging guide. |
| P0 | Staging sharing production resources | **Closed by owner decision:** isolated Railway/Neon/Clerk. |
| P1 | Liveness only | **Closed in plan:** `/ready` separate from `/health`. |
| P1 | Leftover ALTER / `create_all` | **Closed in plan:** disabled for staging/production startup. |
| P1 | Context still said draft PR #1 | **Closed:** mutable docs record `c3647a4` merged, not deployed. |
| P1 | Incomplete append-only triggers | Deferred until truth apply (named limitation). |
| P1 | Worker HTTP health | Deferred with worker unlock. |
| Open | `MIGRATOR-ROLE-PROVISIONING-GATE` | Remains open until Neon LOGIN proof. Does not block freeze of this plan. |
| Open | `CSV-COST-FEEDBACK-GATE` | Production-only; CSV overwrite stays frozen. |

## Architecture (bounded)

Approved topology is three isolated slice-0 systems (Railway API, Neon, Clerk). Worker/Vercel/Convex out of slice 0. FEATURE_NOT_READY and readiness endpoints belong in the API process, not a sidecar.

## Database-security (bounded)

Role SQL is idempotent and forbids inheritance. It does not close the gate until executed on Neon. Freeze of the plan is allowed; execution is not authorized here.

## Application-security (bounded)

Staging identity fail-closed is already in code if Clerk is configured. Slice 0 adds `/ready` rejection when bypass or debug would be on.

## Data-integrity (bounded)

Slice 0 does not apply truth schema. Quantity writes are unavailable via FEATURE_NOT_READY rather than dual-write 500. Recon = 0 remains a later cutover gate.

## Operations / recovery (bounded)

Chris is incident owner and break-glass approver. Runbook exists. Backup drill remains before truth apply, not before slice-0 create.

## Adversarial (bounded)

Cross-shop 403 tests stay in slice-0 smoke. Synthetic data only. No production clone.

## Workflow-liveness (bounded)

Worker not started. Notification tick off. Liveness probe must not use `/ready` so a missing DB does not crash-loop the process before operators can inspect.

## Final verification (this pass)

| Claim | Result |
| --- | --- |
| Owner decisions 1–7 recorded as approved | `OWNER-DECISIONS.md` |
| FEATURE_NOT_READY specified | `SAFEGUARDS.md` |
| `/health` vs `/ready` specified | `SAFEGUARDS.md`, `SMOKE.md` |
| Startup `create_all`/ALTER contained in staging | `SCHEMA.md` |
| Shopify/worker missing = off | `FLAGS.md`, `ENVIRONMENT.md` |
| `DEPLOY.md` marked outdated | `DEPLOY.md` banner + `RUNBOOK.md` |
| Mutable PR #1 status corrected | `docs/agent-context/*`, notification/inventory gates, integration review header |
| No cloud/provision/commit | This pass documentation only |
| Slice-0 directive excluded from freeze hashes | Issued after freeze |

No remaining P0/P1 **planning** defect blocks freeze. Implementation and provisioning remain locked.
