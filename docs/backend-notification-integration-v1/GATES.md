# Gates — backend-notification-integration-v1

**Packet status:** `1.1.2 BACKEND MERGED TO main AS c3647a4 — REQUIRED CI GREEN — NOT DEPLOYED`

| Gate | Owner | Evidence | Terminal |
| --- | --- | --- | --- |
| Product policy 1.1.0 | Human | Unchanged file `docs/card-resolution-workflow/AMENDMENT-1.1.0.md` | Closed as policy record; file not rewritten |
| AMENDMENT-1.1.1 vote | Human | APPROVE 2026-08-24 including D-N5 at-least-once | **APPROVED AND FROZEN** |
| Freeze 1.1.1 | Human | `freezes/FREEZE-1.1.1.json` + validator + negative checks | **FROZEN 2026-08-24** |
| AMENDMENT-1.1.2 vote | Human | APPROVE 2026-08-24 | **APPROVED** |
| Freeze 1.1.2 | Human | `freezes/FREEZE-1.1.2.json` + validator + negative checks | **FROZEN 2026-08-24** |
| `implementation_unlock` backend-notification-integration-v1 (1.1.0+1.1.1+1.1.2) | Human | Named unlock of `DIRECTIVE-IMPLEMENTATION.md` | **USED** for local 1.1.2 backend; does not authorize push, merge, or deploy |
| Local 1.1.2 backend acceptance | Human | `ACCEPTANCE-1.1.2.md`; two disposable PostgreSQL 16.14 runs 21/21; SQLite 178 passed | **APPROVED 2026-08-25** locally; later included in PR #1 |
| Freeze-evidence checkout correction | CI | `FREEZE-*-git-canonical.json`; historical freeze JSON preserved | **BYTE-HASH ONLY 2026-08-25** — not a product/contract amendment |
| Feature-branch push / PR | Human | `feature/backend-notification-v1.1.2`; PR #1 | **MERGED** as `c3647a4` — not deployed |
| **GITHUB-NOTIFICATION-CI-GATE** | Human + GitHub Actions | Required jobs on exact head `4d317f8` | **SATISFIED for 4d317f8** (sqlite, postgres, contract, contract-and-backend, frontend-build, pg-acceptance). Does not authorize merge or deploy |
| Optional Cursor/OpenAI review jobs | Advisory | `.github/EXTERNAL-AI-REVIEWS.md` | Advisory only. Missing secrets skip the jobs; they do not pass product gates |
| **NOTIFICATION-INTEGRATION-GATE** (backend overlap) | Human + integration reviewer | `docs/integration-reviews/BACKEND-FOUNDATION-PR1.md` | **CLOSED for backend overlap only** on `4d317f8` |
| **FRONTEND-NOTIFICATION-SETTINGS-GATE** | Later named slice | Settings UI, service-worker install, permission UX | Open — deferred |
| **FRONTEND-AUTHENTICATED-API-TRANSPORT-GATE** | Human + frontend | Existing admin/POS callers send Clerk bearer; shop id is a hint | Implemented on `main` via `c3647a4` |
| Production VAPID / live Web Push | Human | Complete server-side VAPID; no Git secrets | Open — **disabled** |
| Production notification schema apply / roles / cutover | Human | Migrator role gate + standing deployment gates | Open |
| **CSV-COST-FEEDBACK-GATE** | Human + API/UI | Ignored existing-item CSV cost must be disclosed before production CSV adjust | **OPEN** — preserved |

Standing: merged to `main` (`c3647a4`), **not deployed**. No production migration, live Web Push, or production credentials.
