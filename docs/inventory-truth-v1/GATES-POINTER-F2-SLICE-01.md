# Gate pointer — F2 slice-01 controlled receive (staging provisioning)

Frozen `GATES.md` is unchanged. This pointer records later owner evidence for
the F2 slice-01 gates (see `GATES.md` §“F2 slice-01”).

**Provisioning unlock (staging schema apply):** **CLOSED on staging** 2026-09-04.
Column `client_idempotency_key`, partial unique index
`uq_purchase_record_shop_client_key`, and the `stashtab_api` least-privilege
envelope are applied on Neon `stashtab_staging` only, owned by
`stashtab_migrator`. Provisioning was completed during an authorized Cursor run
that was interrupted before its report; Qoder reconciled and verified it
read-only. An idempotent rerun produced no schema/index change (before/after
snapshots byte-identical). All business tables remain empty; identity intact
(2 shops / 2 owners); no `F2-TEST-0001`; cutover row absent. No rollback,
deploy, seed, receive, or production action.
Evidence: `CHECKPOINT-F2-SLICE-01-STAGING-PROVISIONING.md`;
`ACCEPTANCE-F2-SLICE-01-CONTROLLED-RECEIVE.md`; D-042.

**Cutover unlock (gen-1 synthetic shop):** **STILL OPEN — separately locked.**
Provisioning does not unlock cutover. No `inventory_truth_cutover` row exists.

**Receive-endpoint use:** **STILL LOCKED.** `POST
/api/v1/admin/inventory/receive` must not succeed until cutover is unlocked;
authenticated calls fail closed with a controlled 503 before any write.
**Observed 2026-09-04:** exactly one owner-run authenticated probe returned
`503` `FEATURE_NOT_READY` (`feature: inventory_truth`) after authentication and
membership resolution (`GET /api/v1/shops/me/memberships` → `200`) and before
any receive transaction or write; the earlier unauthenticated probe returned
`401`. No receive row exists.

**API deployment (Railway staging, API only):** **EXECUTED AND VERIFIED —
FAIL-CLOSED** 2026-09-04. Protected `main` at `ec9f72c` deployed once as Railway
deployment `44317623` (`SUCCESS`); `meta.commitHash` matched the pinned SHA;
autodeploy stayed off (`watchPatterns: []`); one API service instance, no
worker, no cron. Health and ready both `200`, all feature flags `false`
(including `inventory_cutover`), one stable process, zero worker/Shopify/
notification/Web Push/schema/migration/seed activity. Pooled-`stashtab_api`
read-only Neon re-snapshot: row-count digest
`7f92454515ec31678e05a1da695f1bb02ddba0b7f67a648db008566b22d066c9` unchanged,
all business/truth tables `0`, `shops = 2` / `shop_members = 2`, cutover rowcount
`0`, both `F2-PROBE-DO-NOT-USE` and `F2-TEST-0001` absent, and the F2 column,
partial unique index, and grant envelope unchanged.
See `CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`; D-043.

**Cutover planning:** **PREPARED — PLANNING ONLY.**
`CHECKPOINT-F2-CUTOVER-PLANNING.md` lists the preconditions and evidence a
future cutover unlock must satisfy. It does **not** approve or execute cutover.

## Non-F2 baseline follow-ups (not F2 claims)

Pre-existing least-privilege observations on staging, unrelated to and **not**
introduced by the F2 envelope. Recorded for a future runtime-grant review; not
a defect claim and not a blocker for this slice:

- Runtime `stashtab_api` holds **INSERT** on the identity tables `shops` and
  `shop_members` (identity-kernel baseline).
- Runtime `stashtab_api` holds **USAGE / SELECT / UPDATE** on the non-F2 truth
  sequences (`sale_id_seq`, `inventory_adjustment_id_seq`,
  `inventory_channel_observation_id_seq`, `inventory_exception_id_seq`,
  `inventory_truth_cutover_id_seq`, `refund_record_id_seq`,
  `return_record_id_seq`) while the corresponding tables stay SELECT-only.

Still open:

- Cutover unlock and any receive / inventory write on staging (planning
  checkpoint prepared; not approved, not executed).
- The two non-F2 baseline privilege follow-ups above.
- Production provisioning, cutover, and deploy (all blocked by
  `MIGRATOR-ROLE-PROVISIONING-GATE` and the standing deployment gates).

Closed since the provisioning record: the F2 API deployment to Railway staging
(executed and verified fail-closed, above).
