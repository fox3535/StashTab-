# Notification integration planning report

**Status:** PLANNING ONLY — no merge, stash, discard, or rewrite of the
preserved notification worktree.
**Inspected:** original worktree `C:\Users\Chris\Desktop\Cursor Projects\mimir-saas2`
on `checkpoint/inventory-truth-v1.1.0`.
**Inventory checkpoint:** slice-03 worktree
`feature/inventory-truth-slice-03` at planning commit `6370060`.

## Original worktree

- Branch: `checkpoint/inventory-truth-v1.1.0`
- Notification modules are mostly **untracked**; several frontend/API
  client files are **modified** and uncommitted.
- This tree must stay untouched until a named integration unlock.

## Notification-related files (preserved)

Untracked (core notification implementation):

- `services/api/app/logic/notifications.py`
- `services/api/app/logic/push_endpoints.py`
- `services/api/app/models/notification.py`
- `services/api/app/routers/notifications.py`
- `services/api/tests/test_notifications.py`
- `public/sw.js`
- `components/notification-settings.tsx`
- `hooks/use-api-auth.ts`

Modified and likely notification/auth related:

- `app/admin/settings/page.tsx`
- `lib/admin-api.ts`
- `lib/mimir-api.ts`
- `package.json` / `package-lock.json` (one dependency line)

Committed on this checkpoint and already importing notifications:

- `services/api/app/main.py` (includes notifications router)
- `services/api/worker.py` (`process_pending_notifications`)
- `services/api/app/deps.py` (`get_notification_context`)
- `services/api/tests/test_identity.py` (notification router + worker stub)
- `services/api/requirements.txt` (`pywebpush>=2.0.3`)

## Unrelated or uncertain

- `scripts/run_cursor_review.mjs` — review helper, not notification runtime.
- Generated barcode PNGs under `services/api/app/static/barcodes/` — artifacts.
- Other modified admin pages (`dashboard`, `intake`, `paperweight`,
  `reconciliation`, `reports`, `resticker`, `shopify/*`, `staging`,
  `onboarding`, `pos/pos-context.tsx`) — may be shared auth-header wiring
  via `use-api-auth` / `lib/*-api.ts`. Treat as **manual review**, not
  auto-merge, until a human confirms they are only auth plumbing.

## Overlap with accepted inventory checkpoint

Must reconcile by hand, not blindly merge:

| File | Original | Slice-03 inventory tree |
| --- | --- | --- |
| `services/api/app/main.py` | imports and mounts notifications | outbound/adjust tree removed those imports |
| `services/api/worker.py` | calls `process_pending_notifications` | inventory worker has shop isolation, no notification tick |
| `services/api/app/deps.py` | `get_notification_context` present | also present; confirm identical before merge |
| `services/api/tests/test_identity.py` | notification imports | inventory tree stripped dangling imports |
| Admin PATCH / CSV (`admin.py`, `import_engine.py`) | unmodified notification tree | slice-03 adjustment writer |
| `package.json` | +1 frontend dependency | inventory checkpoint may lack it |

P0/P1 notification corrections still present in original untracked code:
HTTPS-only endpoints, host allowlist, `no_redirect_session`, metadata-host
denylist, tests for evil URLs / loopback / 409 endpoint reuse.

## Tests (original tree, inspect-only)

`pytest tests/test_notifications.py` in the original worktree: **28 passed**.
No files were changed. Identity tests in that tree import the
notifications router; they were not re-run here.

## Safest integration order

1. Keep notification tree frozen as-is (no stash/discard).
2. Branch from the accepted slice-03 checkpoint.
3. Copy/add untracked notification modules and tests.
4. Manually restore notification mounts in `main.py` and the worker tick
   **on top of** slice-02/03 worker isolation (do not revert inventory
   worker isolation).
5. Reconcile `deps.py` and `test_identity.py` by hand.
6. Reconcile frontend auth helpers and settings page by hand.
7. Run notification tests, identity tests, and inventory PG/SQLite
   suites together.
8. Only then consider merge. Both suites must pass.

## Rollback

Leave the original worktree unmodified. If an integration branch fails,
delete that branch; the preserved notification files remain in the
original tree.

## Human decisions

1. Confirm whether the other modified admin/POS pages are auth-only or
   unrelated product edits.
2. Whether `scripts/run_cursor_review.mjs` belongs in the integration.
3. Named unlock to perform the integration (this report does not unlock it).
