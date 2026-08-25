# Gates — backend-notification-integration-v1

**Packet status:** `1.1.2 BACKEND ACCEPTED LOCALLY — NOT PUSHED — NOT MERGED — NOT DEPLOYED`

| Gate | Owner | Evidence | Terminal |
| --- | --- | --- | --- |
| Product policy 1.1.0 | Human | Unchanged file `docs/card-resolution-workflow/AMENDMENT-1.1.0.md` | Closed as policy record; file not rewritten |
| AMENDMENT-1.1.1 vote | Human | APPROVE 2026-08-24 including D-N5 at-least-once | **APPROVED AND FROZEN** |
| Freeze 1.1.1 | Human | `freezes/FREEZE-1.1.1.json` + validator + negative checks | **FROZEN 2026-08-24** |
| AMENDMENT-1.1.2 vote | Human | APPROVE 2026-08-24 | **APPROVED** |
| Freeze 1.1.2 | Human | `freezes/FREEZE-1.1.2.json` + validator + negative checks | **FROZEN 2026-08-24** |
| `implementation_unlock` backend-notification-integration-v1 (1.1.0+1.1.1+1.1.2) | Human | Named unlock of `DIRECTIVE-IMPLEMENTATION.md` | **USED** for local 1.1.2 backend; does not authorize push, merge, or deploy |
| Local 1.1.2 backend acceptance | Human | `ACCEPTANCE-1.1.2.md`; two disposable PostgreSQL 16.14 runs 21/21; SQLite 178 passed | **APPROVED 2026-08-25 — NOT PUSHED — NOT MERGED — NOT DEPLOYED** |
| Freeze-evidence checkout correction | CI | `FREEZE-*-git-canonical.json`; historical freeze JSON preserved | **BYTE-HASH ONLY 2026-08-25** — not a product/contract amendment |
| **GITHUB-NOTIFICATION-CI-GATE** | Human + GitHub Actions | Blocking PostgreSQL notification workflow must run green on the exact pushed commits | **OPEN — BLOCKS merge and deployment**. Unexecuted workflow file is not execution evidence |
| Optional Cursor/OpenAI review jobs | Advisory | `.github/EXTERNAL-AI-REVIEWS.md` | Advisory only. Missing secrets skip the jobs; they do not pass product gates |
| **NOTIFICATION-INTEGRATION-GATE** | Human + integration reviewer | Overlapping identity/inventory files remain reviewed before merge; both suites green | Open — **BLOCKS merge and deployment** |
| Production VAPID / live Web Push | Human | Complete server-side VAPID; no Git secrets | Open — **disabled** |
| Production notification schema apply | Human | Migrator role gate + standing deployment gates | Open |
| Frontend settings / service worker / permission UX | Later named slice | Out of this freeze | Out of scope |

Standing: no push, merge, deploy, production migration, live Web Push, or production credentials from this acceptance.
