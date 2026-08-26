# Feature flags and enablement owners

Every enablement: named owner, written evidence, and a disable path.

| Flag / control | Slice 0 | Who may enable later | Evidence required |
| --- | --- | --- | --- |
| `APP_ENV=staging` | Required at first boot | Owner | Process starts; bypass rejected |
| Debug off | Required at first boot | Owner | `/ready` shows debug false |
| Inventory freeze / cutover complete | Off | Owner after recon = 0 | Freeze log + recon report |
| Receive / POS / adjust / outbound | Unavailable (`503 FEATURE_NOT_READY`) | Owner after gen-1 | Dual-write tests on synthetic shop |
| `NOTIFICATIONS_BACKEND_ENABLED` | **false** | Owner after notification schema + mocked transport | 404 then durable intent without Web Push |
| VAPID / Web Push | Empty | Production-only later | `PRODUCTION-VAPID-GATE` |
| Worker process | **Not provisioned** | Separate unlock | Job-by-job |
| Shopify auto-sync | Off; no tokens | Separate unlock | Disposable development store only; missing tokens = off |
| Notification tick on worker | Off | After backend flag | Mocked transport |

## Fail-closed worker / Shopify (required in slice-0 code)

- Missing `system_settings` → treat auto-sync as **off** (never on).
- Missing or empty Shopify tokens → no Admin API calls.
- Worker not running in slice 0; these defaults must still be in code before any worker unlock.

## Default-on traps (must not ship into staging)

- `notifications_backend_enabled` defaults false. Keep false.
- `debug` defaults true. Staging must set false; `/ready` must fail if debug is on.
- Extra push host suffixes refuse to start. Keep unset.
- `STASHTAB_TRUTH_MIGRATOR_ROLE` unset on API and worker.
