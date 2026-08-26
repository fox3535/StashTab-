# Open gates (classified)

**Packet status:** owner decisions approved 2026-08-25; freeze hashes in `freezes/FREEZE-v1.json`.  
**Code baseline:** `main` `c3647a4eda37d355ed47f9e77ad667e4fda7930c` — merged, **not deployed**.

## Required before staging resources may be created

| Item | Status |
| --- | --- |
| Isolated Railway + Neon + Clerk (no production share) | Approved; not provisioned |
| No production clone / no production PII | Approved |
| First-boot flags (`APP_ENV=staging`, debug off, bypass off, notifications off, no VAPID, no worker, no Shopify) | Approved |
| `DEPLOY.md` not used as staging guide | Closed in this packet (`RUNBOOK.md`) |
| Mutable docs: PR #1 merged, not deployed | Closed alongside this freeze |

## Required before slice-0 API is trusted (implementation, not this freeze)

| Item | Status |
| --- | --- |
| `503 FEATURE_NOT_READY` on truth-dependent routes | Specified in `SAFEGUARDS.md`; code in slice 0 |
| `/ready` separate from `/health` | Specified; code in slice 0 |
| No startup `create_all` / leftover ALTER in staging | Specified; code in slice 0 |
| Worker/Shopify missing settings = off | Specified; code in slice 0 (worker still not provisioned) |
| Identity + shop-isolation smoke | Slice 0 after provision |

## Required before staging migration (inventory-truth / notification schema)

| Gate / item | Why |
| --- | --- |
| `MIGRATOR-ROLE-PROVISIONING-GATE` on **this** Neon | Runtime LOGIN proof |
| Membership unique index verified | Identity gate |
| Empty + synthetic rehearsal A/B | `REHEARSAL.md` |
| Runtime cannot `CREATE ROLE` | Inventory migrator trap |
| Backup/restore drill | `REHEARSAL.md` C |

Not slice 0.

## Required before staging feature enablement

| Control | Before |
| --- | --- |
| Receive / POS / adjust / outbound | Gen-1 complete + recon = 0 + later unlock |
| Worker | Slice 0 identity proven; Shopify tokens absent; fail-closed defaults in code |
| Shopify sandbox | Named development store only; missing tokens = off |
| Notification backend | Notification schema + mocked transport + later unlock |

## Required only before production

| Gate | Notes |
| --- | --- |
| `CSV-COST-FEEDBACK-GATE` | Frozen open. Staging may exist if CSV overwrite stays frozen. |
| Zero recon on **production** data | Staging synthetic recon does not close this |
| `PRODUCTION-VAPID-GATE` | Live Web Push |
| DNS pinning for custom hosts | When extra push suffixes are introduced |
| Security-assurance program | Org-wide |
| Second qualified human owner | Required before production readiness |
| Card-resolution core | Not this packet |

## Deferred product / frontend

Notification UI + service worker; Vercel staging; Convex staging; production customer data; closing `CSV-COST-FEEDBACK-GATE`.
