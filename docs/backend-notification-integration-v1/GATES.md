# Gates — backend-notification-integration-v1

**Packet status:** `FROZEN AMENDMENT 1.1.1 + BACKEND PLAN — IMPLEMENTATION AWAITING NAMED UNLOCK`

| Gate | Owner | Evidence | Terminal |
| --- | --- | --- | --- |
| Product policy 1.1.0 | Human | Unchanged file `docs/card-resolution-workflow/AMENDMENT-1.1.0.md` | Closed as policy record; file not rewritten |
| AMENDMENT-1.1.1 vote | Human | APPROVE 2026-08-24 including D-N5 at-least-once | **APPROVED** |
| Freeze | Human | `freezes/FREEZE-1.1.1.json` + validator + negative checks | **FROZEN 2026-08-24** |
| `implementation_unlock` backend-notification-integration-v1 | Human | Named unlock of `DIRECTIVE-IMPLEMENTATION.md` | **OPEN — BLOCKS code** |
| **NOTIFICATION-INTEGRATION-GATE** | Human + integration reviewer | Hand-reconcile overlapping `main.py` / `worker.py` / identity tests with preserved original-worktree backend files after unlock; both suites green | Open — **BLOCKS merge and deployment** |
| Production VAPID / live Web Push | Human | Complete server-side VAPID; no Git secrets | Open — **disabled** |
| Production notification schema apply | Human | Migrator role gate + standing deployment gates | Open |
| Frontend settings / service worker / permission UX | Later named slice | Out of this freeze | Out of scope |

Standing: no commit/push/merge/deploy/migration/production credentials from this freeze action.
