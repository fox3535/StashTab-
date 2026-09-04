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

**API deployment (Railway staging, API only):** **PREPARED — NOT EXECUTED.**
See `CHECKPOINT-F2-API-DEPLOYMENT-PRE-CUTOVER.md`.

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

- Cutover unlock and any receive / inventory write on staging.
- F2 API deployment to Railway (prepared checkpoint above).
- The two non-F2 baseline privilege follow-ups above.
- Production provisioning, cutover, and deploy (all blocked by
  `MIGRATOR-ROLE-PROVISIONING-GATE` and the standing deployment gates).
