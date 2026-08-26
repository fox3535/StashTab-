# Operations (staging)

Incident owner / break-glass approver: **Chris**. Second qualified human required before production readiness.

## What exists today (code on `main`, not hosted)

- API liveness: `GET /api/v1/health`
- Railway `healthcheckPath` uses that path
- Worker has no HTTP health endpoint (worker not in slice 0)
- Readiness and FEATURE_NOT_READY are specified in `SAFEGUARDS.md` and implemented in slice 0

## Staging operable minimum

| Need | Staging minimum |
| --- | --- |
| Structured logs | `shop_id` on identity denials; no secrets |
| `/health` vs `/ready` | Liveness vs DB/identity/gates |
| Alerts | Page on 5xx spike, identity fail-closed at boot, `/ready` 503 |
| Runbook | `RUNBOOK.md` — not `DEPLOY.md` |
| Break-glass | Chris; time-bounded; log; rotate after |
| Credential revocation | Rotate Neon api/worker/migrator passwords; strip Railway env; restart; confirm old URLs fail; revoke Clerk staging secret if leaked |

## Worker (later unlock only)

Heartbeat or log line. Stopped worker is not silent. Missing settings = jobs off.
