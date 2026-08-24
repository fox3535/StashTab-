# Planning reviews — backend-notification-integration-v1

**Baseline:** `3a78278`  
**Source inspected:** original `checkpoint/inventory-truth-v1.1.0` (read-only)  
**Correction budget:** one pass, then final verification.

## Architecture

**Verdict:** PASS after correction.

Cite: original `worker.py` runs notifications after auto-sync but **inside** `tick_shop` with no per-shop catch; slice-03 `worker.py` isolates shops but **omits** notifications. DIRECTIVE §10 requires both: always tick notifications, isolate failures.

Cite: `create_notification` is only called from the test route today (`routers/notifications.py`), not from inventory writers — good. DIRECTIVE §4.13 forbids later in-transaction coupling.

Boundary is FastAPI + worker; no frontend in this slice.

## Data-integrity

**Verdict:** FINDINGS → corrected in DIRECTIVE.

P0: `process_pending_notifications` orders `created_at.desc()` and limits 100 — newest-first can hide older due rows (requirement 15). Correction: due-time ASC.

P0: `_finalize_event` can leave `pending` when some devices `sent` and others terminal `failed`. Correction: §4.6.

P0: `_reset_deliveries` deletes rows on reopen — loses audit (requirement 7). Correction: new delivery generation / occurrence uniqueness; no DELETE.

Unique `(shop_id, dedupe_key)` is the durable race control; in-memory locks are not enough across processes (requirement 9).

## Application-security

**Verdict:** PASS with P1 notes.

Cite: `get_notification_context` requires Bearer when JWT issuer is set (`deps.py`). Headers are hints only via `get_shop_context`.

Cite: `lock_screen_copy` + `SAFE_TEMPLATES` strip caller title/body. `safe_action_url` forces `/admin/` relative paths.

P1: subscribe path should validate endpoint with the same HTTPS/allowlist rules before insert (router already calls `validate_push_endpoint`). Send path must use `resolve_dns=True` (session already does).

P1: implement 1.1.0 item 9 now: non-owner cannot disable critical.

Ack/resolve do not touch inventory tables (router only updates notification events). Keep that isolation in tests.

## Database-security

**Verdict:** FINDINGS → corrected in DIRECTIVE.

P0: `init_db()` uses `create_all` plus ad-hoc `ALTER TABLE ... IF NOT EXISTS` (`database.py`). That is not an acceptable production lifecycle for notification tables (requirement 16). Correction: dedicated idempotent migrator; tests that startup create_all is not the owner.

Shop_id on all four tables is present. Composite unique on deliveries exists; reopen collision needs occurrence in the unique key.

Runtime role must not UPDATE other shops’ rows; all queries filter `shop_id` from context or Shop.id.

## Adversarial / concurrency

**Verdict:** FINDINGS → corrected.

P0: in-memory `_dedupe_locks` do not work across API workers. Unique + IntegrityError retry is the real lock.

P1: test-send commits then immediately `process_pending` while worker may also tick — unique delivery key prevents double-sent if status is checked in the same transaction; DIRECTIVE requires due-check after lock/unique.

P1: DNS rebinding: literal IP deny exists; send-time resolve exists. Do not skip resolve on send.

## Operations / rollback

**Verdict:** PASS.

Feature flag off by default. Tables empty if worker not mounted. Original tree remains source backup. Inventory schema untouched. No production VAPID in tests (28 tests passed with mocks).

## Workflow-liveness

**Verdict:** PASS after queue-order and terminal-state corrections.

Closed path in DIRECTIVE §13: one planning correction, one freeze check, named implementation unlock. Timeout ≠ success.

Worker continues on failure; backoff does not select future `next_retry_at` rows as the only batch.

## Bounded correction pass (applied to the plan, not to code)

1. Queue order: oldest due first.  
2. Event terminalization when no device is retrying.  
3. Reopen without deleting deliveries.  
4. Migrator-owned schema.  
5. Notification tick independent of auto-sync, per-shop isolated.  
6. After-commit emission vs inventory writes.  
7. AMENDMENT-1.1.1 as a new file, 1.1.0 left intact.

## Final verification

All 20 owner items have an explicit plan clause. Reviews cited original worker, process_pending, `_reset_deliveries`, `init_db`, and `get_notification_context`. No code was copied or edited in either worktree except these planning documents on the slice-03 tree.

**Freeze recommendation:** READY FOR FREEZE CHECK of this DIRECTIVE + AMENDMENT-1.1.1, after human answers in DIRECTIVE §15.
