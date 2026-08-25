# Backend foundation PR #1 — integration synthesis

**Status:** review evidence. Included in the merge-readiness pass after owner approved one foundation PR.

## Merge-readiness follow-up (after `4d317f8`)

Owner approved **one foundation PR**. This pass does not split history.

| Item | Result |
| --- | --- |
| Extra/custom push-provider hosts | Disabled. Non-empty `WEB_PUSH_ALLOWED_HOST_SUFFIXES` is a config error. Frozen allowlist only. No DNS pinning added. |
| Gate records | Mutable gates/context updated: branch pushed, draft PR #1, required CI at `4d317f8`, backend overlap closed, CSV cost gate preserved. Frozen contract bodies unchanged. |
| Frontend auth transport | Existing admin/POS/onboarding callers send Clerk `Authorization: Bearer`. Shop id remains a hint. No `X-Clerk-User-Id` on protected browser calls. Missing token surfaces a sign-in/session-expired state. |

`4d317f8` remains the reviewed integration head. Later commits on this draft are merge-readiness corrections only.

---  
**PR:** https://github.com/fox3535/StashTab-/pull/1  
**Head:** `4d317f8b3f06e5f69c5fce29b1c7de6ff90ecdca` (`4d317f8`)  
**Base:** `main` / `e5ed96b43234b0816d3320a69ae6fd0ddc2ded22`  
**Draft:** yes. **Merged:** no.  
**Diff:** 147 files, +24027 / −255 versus `main`.

This file records a review-only assessment of the **full** `main...HEAD` diff. Ten independent review lanes were used (architecture, identity, schema/migrations, inventory, notifications, workers, API security, operations, adversarial overlap, PR structure). Claims below were re-checked against the tree at this head. No product, test, workflow, contract, or documentation files were changed except this file.

---

## Preconditions

| Check | Result |
| --- | --- |
| PR remains draft | Yes |
| Head is exactly `4d317f8` | Yes (`4d317f8b3f06e5f69c5fce29b1c7de6ff90ecdca`) |
| Base is `main` | Yes |
| Tracked working tree | Clean (no staged/unstaged edits to tracked files) |
| Untracked local noise | Barcode PNGs under `services/api/app/static/barcodes/` and `tmp-ci-diag/` — not part of the PR |
| Required GitHub jobs on this head | sqlite, postgres, contract, contract-and-backend, frontend-build, pg-acceptance — all success |
| Advisory Cursor/OpenAI jobs | skipped (no keys); secret_probe and advisory_status success |
| Merge / deploy / production migration / live Web Push | None |

`docs/backend-notification-integration-v1/GATES.md` still says the packet was not pushed. That document is stale relative to this draft PR. It is **not** evidence that GitHub CI never ran. Required jobs on this head did run and passed.

---

## Combined-tree verdict

Backend overlap for identity, inventory-truth, and notification 1.1.2 **can be accepted as reviewed together** on this head.

- Production HTTP shop/user identity is JWT plus membership. `X-Shop-Id` is a selector among memberships. `X-Clerk-User-Id` is not a credential unless the local/test bypass is on.
- The worker uses persisted `Shop.id`, never request headers.
- Notification recover **selects** open inventory exceptions and writes notification rows. Acknowledge/resolve/cancel do not close inventory exceptions.
- Worker tick keeps inventory sync isolated from the notification session and still ticks notifications when auto-sync is off (when the notification flag is on).
- Truth and notification tables are not on application `Base`; tests assert `create_all` does not create them.
- Web Push stays off without complete VAPID (`services/api/app/config.py`).
- Deferred frontend notification settings / service worker are **not** in this PR and are not imported by Python.
- `CSV-COST-FEEDBACK-GATE` remains **open**. Cost on existing-item CSV is not applied. Success payload still does not disclose the ignore. That gate must stay open.

No P0 was found that would reverse the combined-backend overlap review.

Remaining items are merge, production-schema, or deferred-frontend work. They are listed below. They are **not** treated as already done.

---

## Explicit verification

| Question | Result |
| --- | --- |
| Identity on affected routes | Shop-scoped routers use `get_shop_context`. Notification mutating routes use `get_notification_context` (Bearer required when Clerk issuer is set). Health and `/notifications/config` (when mounted) are unauthenticated by design. |
| Production trusts caller shop/user headers? | No. Bypass requires `APP_ENV` `local` or `test` **and** `STASHTAB_ALLOW_DEV_IDENTITY`. Staging/production/missing env refuse it. |
| Background jobs | `services/api/worker.py` iterates `Shop` rows and passes `shop.id`. |
| Inventory receive / outbound / adjust | Separate cores, same `inventory_event` stream, shop-scoped keys. Snapshot `InventoryItem.stock` still exists as the operational quantity; dual-write is by design for this foundation. |
| Notification cannot resolve inventory | `test_20_acknowledge_does_not_resolve_inventory_exception`; ack/resolve only mutate notification event + audit. |
| Worker isolation + always-tick | Sync failure rolls back the sync session; notification uses a new session. Auto-sync off still recovers/processes when `notifications_backend_enabled`. Default flag is **false**, so production ticks skip notifications until enabled. |
| Migrator order vs `create_all` | Inventory: unique `(shop_id, id)` on live parents, then truth tables, then append-only triggers. Notification apply is one transaction. Startup `init_db()` still `create_all`s **legacy** `Base` and runs inherited `ALTER TABLE ... IF NOT EXISTS` in `services/api/app/database.py`. That path must not be how truth/notification schema is applied in production. |
| Runtime vs migrator roles | Notification grants fail if the runtime role is missing. Inventory migrator can `CREATE ROLE ... NOLOGIN` when `STASHTAB_TRUTH_MIGRATOR_ROLE` is set and missing. **MIGRATOR-ROLE-PROVISIONING-GATE** stays open. |
| Same-shop FKs / uniqueness | Truth and notification child tables are shop-scoped. `ShopMember` uniqueness is on the model; existing production DBs still need the documented unique index apply. |
| Upgrade path | Additive. Rollback of the **flag** unmounts the router and skips recover/process; it does not DROP tables. Production rollback must not DROP accepted evidence. |
| Deferred frontend required by backend? | No. `notification-settings`, `sw.js`, and `use-api-auth` are absent from this commit. |
| Web Push without config | Off. Placeholder `mailto:ops@example.com` does not enable it. |
| CI tests combined code | Notification sqlite job runs `python -m pytest tests -q` (full combined SQLite). PostgreSQL jobs are split: notification PG files vs `test_pg_acceptance.py`. Same PR paths trigger both. Combined PostgreSQL worker+notify in one job is still a gap. |
| Freeze manifests | Frozen JSON is in the tree. Git-canonical hashes are what CI uses. Historical Windows hashes were preserved. |
| `CSV-COST-FEEDBACK-GATE` | Preserved **open**. |
| `NOTIFICATION-INTEGRATION-GATE` | Backend overlap on this head is reviewed. Original text also named frontend files that are **not** in this PR. Close the **backend-overlap** clause; replace the remainder with a scoped frontend/deploy/VAPID/schema gate. |
| Production-only gates completed? | No. Schema apply, migrator-role provisioning, live VAPID, live Web Push, CSV production use, and human deploy approval remain open. Local acceptance is not production. |

---

## Mutation and dependency audit

| Probe | What we saw |
| --- | --- |
| Direct stock writes | `InventoryItem.stock` is still the snapshot. Inventory-truth cores write events/adjustments. Dual-write remains. Not a surprise; production cutover still has its own gate. |
| Shop/user headers | Read in `services/api/app/deps.py`. Production user from JWT. Shop hint cannot open a non-member shop. |
| `create_all` | Legacy `init_db()`. Truth/notification models on separate bases. Tests forbid app `create_all` from creating those tables. |
| Schema SQL outside migrators | Inherited `_ensure_columns` ALTERs on `sale` / `system_settings`. Pre-existing live-app pattern. Not a substitute for truth/notification migrators. |
| Notification ack/resolve | Notification rows and audit only. |
| Worker entry points | `worker.py` loop; HTTP test-send also calls process for that shop. |
| Feature flags | `notifications_backend_enabled` default false. Unmounts router; skips recover/process. |
| Secrets / VAPID | Env settings only. No private VAPID in git. Extra host suffixes are **concatenated** onto the frozen list (`services/api/app/logic/push_endpoints.py`), which contradicts AMENDMENT-1.1.2 R13 (“extra configured suffixes are ignored”). HTTP send re-validates then uses `requests` hostname connect (re-resolve), also short of R13’s “connect to the validated tuple”. |
| Frontend imported by backend | None. |

---

## Findings by class

### P0 / P1 — blocking this integration acceptance

None for **combined backend overlap** (identity + inventory-truth + notification backend on this head, required CI green).

### Required before merge

1. Treat AMENDMENT-1.1.2 R13 as incomplete: extra suffixes must be ignored; send path must not re-resolve after DNS validation. Do not enable live push until that matches the freeze or a later amendment exists.
2. Update gate documents that still say “NOT PUSHED” so they match this draft PR and this head’s GitHub results. Do not mark production schema/VAPID/deploy complete.
3. Record that **GITHUB-NOTIFICATION-CI-GATE** *execution* succeeded on `4d317f8` for the required jobs. Unexecuted-workflow language no longer applies to this head.
4. Prefer a combined PostgreSQL job (or documented waiver) so inventory PG and notification PG are not only split jobs.

### Required before production schema apply / deploy

1. **MIGRATOR-ROLE-PROVISIONING-GATE** — do not let production silently `CREATE ROLE`. Provision migrator and runtime roles deliberately. Inventory migrator’s optional `CREATE ROLE` path is not that proof.
2. Human-approved migrator run; no reliance on worker/API `init_db()` for truth/notification tables.
3. Membership unique index on existing databases if not already present.
4. Append-only DB enforcement today covers `refund_record`, `return_record`, `inventory_adjustment` only. `inventory_event` / lots / observations / exceptions are not in that trigger set. Accept that as a named cutover decision or extend it **before** production truth cutover.
5. Rollback = flag off + no DROP of accepted rows.
6. Do not set `notifications_backend_enabled` or real VAPID in production until the above and R13 are closed.

### Deferred frontend

- Settings UI, service worker, permission UX, and remaining admin pages that still send only `X-Shop-Id` (they will 401 against production identity until they send Bearer).
- Not blockers for backend merge if the UI remains deferred and the notification flag stays off.

### Non-blocking follow-up

- Unused `resolve_clerk_user_id` export.
- `debug: bool = True` default in settings (pre-existing).
- Worker `query(Shop).all()` unordered; no per-shop time budget.
- Test-send can process other due deliveries for that shop (cost/abuse after push is on).
- `GET /notifications/config` unauthenticated when the router is mounted (public VAPID only when push is actually enabled).
- Observability is mostly print statements.

---

## Independent review lanes (summary)

1. **Architecture / FastAPI ownership** — FastAPI owns shop operations. Next.js is a client. No Next.js API business logic in this PR. Notification router is flag-gated.
2. **Auth / tenant isolation** — Production identity closed relative to `main` (old header-as-credential path removed). Local bypass is explicit and env-gated.
3. **Schema / migrators / roles** — Separate bases; ordered migrators; leftover live `create_all` + ALTER; optional inventory `CREATE ROLE`.
4. **Inventory integrity** — Receive/outbound/adjust compose on one event stream. Snapshot dual-write remains. CSV cost ignored without disclosure.
5. **Notifications** — Ack/resolve isolated from inventory. Recover is read + notify. Flag-off does not DROP. 1.1.2 R13 not fully implemented.
6. **Workers** — Isolation and always-tick are in `worker.py` when the flag is on. Default off skips the tick. SQLite proves cross-feature isolation; PG suites are split.
7. **API security** — Push fail-closed without VAPID. R13 DNS-pin and suffix-freeze gaps matter only after enablement, but they are freeze gaps now.
8. **Ops** — Production schema/VAPID/CSV/migrator-role gates remain open. Flag-off is the application rollback.
9. **Adversarial overlap** — Notification cannot close inventory exceptions. Inventory sync failure still allows a notification tick. Test-send is the main coupling hazard once push is on.
10. **PR structure** — 147 files is large. The dangerous surface is `worker.py` / `main.py` / `deps.py`. Splitting those onto `main` without notifications recreates the original integration gate.

---

## PR structure recommendation

**Keep one foundation PR onto `main` for the combined backend.**

Splitting into independently mergeable PRs that each land on `main` would recreate the original failure mode: a worker/main that omits notifications, then a later PR that has to re-integrate. That is how `NOTIFICATION-INTEGRATION-GATE` was born.

Ordered **review slices** (not independently production-mergeable worker states) are fine for humans:

1. Identity (`auth/`, `deps.py`, identity tests)
2. Inventory-truth slices 01–03 + inventory CI
3. Notification freeze docs + canonical hashes
4. Notification implementation + `worker.py` / `main.py` flag + notification CI

Only the last slice is the integration commit set. If GitHub stacked PRs are used, **do not merge 1–3 to `main` until 4 is ready**, or keep this single draft PR and use this synthesis as the overlap review.

Splitting *for readability* without merging intermediates **does not** reduce production risk. Merging intermediates **increases** risk.

---

## `NOTIFICATION-INTEGRATION-GATE`

**Backend overlap:** reviewed on `4d317f8`. Required GitHub jobs green. Identity, worker shop id, notification/inventory isolation, and combined SQLite suite hold.

**Do not close the original gate text wholesale.** It named frontend files that this PR does not contain.

**Replacement remainder (new scoped gate):** frontend settings + service worker + Bearer on remaining admin pages; production VAPID; production schema apply; migrator-role proof; live push off until R13 matches.

---

## `CSV-COST-FEEDBACK-GATE`

Remains **open**. Existing-item CSV cost is parsed and discarded. Success JSON does not say cost was ignored. Production CSV adjust use stays blocked.

---

## What this review is not

- Not merge approval.
- Not production schema approval.
- Not VAPID/Web Push enablement.
- Not a claim that GATES.md files were updated.
- Not a substitute for human product-owner merge.

---

*Reviewers did not request external AI with repository secrets. Advisory GitHub Cursor/OpenAI jobs were skipped.*
