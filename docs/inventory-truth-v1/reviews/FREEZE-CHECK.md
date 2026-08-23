# Bounded freeze check

**Package:** `STASHTAB-INVENTORY-TRUTH-001` `0.1.1-locked`  
**Slice:** `inventory-truth-foundation`  
**Date:** 2026-08-20  
**Reviewer:** freeze-check reviewer (not the planner)  
**Kind:** one freeze check against the eight authorized criteria only.  
**Not:** another review cycle. No optional redesign. Packet status left unchanged (`READY_FOR_FREEZE_CHECK`); this check does not set `FROZEN`.

Rubric: each criterion **PASS** only if the packet states the rule
explicitly. FAIL if missing, still OR-ambiguous, or contradicted.
Historical review files were not used as evidence.

## Criterion 1 — One quantity equation — PASS

Packet states one remaining formula, a closed quantity-changing vs overlay split, and that overlay deltas are zero so reserve/release cannot change remaining.

Evidence (`DESIGN.md`):

> QUANTITY_CHANGING = receive | sell | loss | return | damage | adjust | reverse (only if the reversed event is QUANTITY_CHANGING)
>
> OVERLAY = reserve | release | move | channel_commit | quarantine | reverse (only if the reversed event is OVERLAY)
>
> Overlay events MUST set `quantity_delta = 0`. … They **never** enter remaining or recon.
>
> lot_remaining(shop_id, lot_id) = SUM(quantity_delta) FROM inventory_event WHERE shop_id = :shop_id AND lot_id = :lot_id
>
> Because overlay deltas are 0, reserve/release cannot change remaining.

Receive-first writes are limited to `receive`, `loss`, and reverse of those (`DESIGN.md` §1). Tests restated the same remaining rule (`TESTS.md`).

## Criterion 2 — Canonical idempotency key — PASS

One format is shared by live dual-write and historical backfill, with fields, uniqueness boundary, collision handling, and retry stated without an alternate scheme.

Evidence (`DESIGN.md` §2):

> Format (exact): `{source}:{shop_id}:{source_pk}`
>
> Opening and shrinkage append `:gen:{n}` (this slice uses `n=1` only)
>
> `purchase_record` | `purchase_record.id` | Live trade dual-write **and** purchase backfill
>
> Uniqueness boundary: `UNIQUE (shop_id, idempotency_key)` on `acquisition_lot` **and separately** on `inventory_event`.
>
> Same string on both tables is required
>
> No `:receive` suffix. No “prefix” alternative.

Retry/collision is a five-step procedure: one transaction for lot then event; matching pair is no-op; lot-without-event inserts the missing event with the same key; event-without-lot is `failed_permanent`; unique violation is a retry of that pair and does not add quantity (`DESIGN.md` §2). Backfill uses the same keys and points collision/retry at that section (`MIGRATION.md` “Backfill (same keys as live dual-write)”). `TESTS.md` requires live dual-write and purchase backfill to share `purchase_record:{shop_id}:{id}` with no `:receive` suffix.

## Criterion 3 — Same-shop keys and composite FKs — PASS

Prerequisite unique `(shop_id, id)` keys, validation order, and same-shop composite FKs are stated for every live table lots/events reference.

Evidence (`DESIGN.md` §3):

> 1. Validate: no duplicate `(shop_id, id)` (vacuous if `id` is the PK).
> 2. `CREATE UNIQUE INDEX` `(shop_id, id)` on live: `inventory_item`, `purchase_record`, `sale`.
> 3. Then create new tables with `UNIQUE (shop_id, id)`.
> 4. Then create composite FKs.

Live parents referenced by lots/events are those three tables. Child FKs are listed as `(shop_id, …)` to `inventory_item`, `purchase_record`, `sale`, `acquisition_lot`, and self-`inventory_event`, all `ON DELETE RESTRICT` (`DESIGN.md` §3). `staging_item` is not an FK target after delete (`DESIGN.md` §3). `MIGRATION.md` Compatibility restates the additive unique indexes before new tables and FKs.

## Criterion 4 — `create_all` must not create new models — PASS

New inventory models are excluded from startup `create_all`, with a migrator-only import path and an acceptance check.

Evidence (`MIGRATION.md` §4):

> `AcquisitionLot`, `InventoryEvent`, and `InventoryTruthCutover` MUST live in a module that is **not** imported by `app.models`, `app.models.__init__`, `app.database`, `app.main`, or `worker`.
>
> The approved migrator is the **only** process that imports that module and applies DDL.
>
> Acceptance check (must fail the PR if red): start the API `init_db` path against an empty schema fixture. Assert tables `acquisition_lot`, `inventory_event`, and `inventory_truth_cutover` **do not exist**. Run the migrator. Assert they **do exist**.

`TESTS.md` requires the same `init_db` / application `create_all` check.

## Criterion 5 — Closed planning path and gates — PASS

The closed path is stated, and every planning/freeze gate has owner, evidence, deadline/attempt limit, and terminal outcome.

Evidence (`INDEX.md`):

> CORRECTION_IN_PROGRESS → READY_FOR_FREEZE_CHECK → FROZEN | REJECTED
>
> No return to open review.

Evidence (`GATES.md` planning path table):

> `CORRECTION_IN_PROGRESS` | Planner | Locked wording covering the eight freeze criteria | This authorized pass only (1) | → `READY_FOR_FREEZE_CHECK`
>
> `READY_FOR_FREEZE_CHECK` | Freeze-check reviewer ≠ planner | Pass/fail on the eight criteria only; no redesign | 1 attempt | Pass → status `READY FOR FREEZE APPROVAL`. Fail → `REJECTED — OWNER ACTION REQUIRED`
>
> Freeze decision | Executive sponsor | Freeze-check file | 14 days; 0 retries of review | `FROZEN` or `REJECTED`

Timeout is never success; a failed freeze check names the failed criterion and owner and stops (`GATES.md`). After-freeze gates are out of this pass and are also fully specified.

## Criterion 6 — Shrinkage is loss, not a Sale — PASS

Negative opening gap and shrinkage use an explicit `loss` event. A Sale row is forbidden.

Evidence (`MIGRATION.md` Backfill B):

> If `gap < 0`: one shrinkage lot with `quantity_acquired = abs(gap)` and one `loss` event `quantity_delta = -abs(gap)`. Reason `backfill_shrinkage_provisional`. **Not a Sale. Do not insert a `Sale` row.**

Evidence (`DESIGN.md` §1):

> No `Sale` row is created for `loss`.

Evidence (`TESTS.md`):

> Inventory **loss** / shrinkage is event type `loss`. It MUST NOT create a `Sale` row. Sale count unchanged.
>
> SKU with extra purchase qty vs stock → `loss` (not sell, not Sale).

No remaining “shrinkage sell” path is stated in the packet.

## Criterion 7 — Opening-gap vs live-receive race — PASS

Cutover watermark, freeze, row locking, deterministic recon, and safe retry close the race.

Evidence (`MIGRATION.md` Order):

> Freeze first for that shop: reject staging commit, trade receive, POS finalize, Shopify stock pull/push, admin PATCH stock, and CSV stock overwrite. Dual-write code may be deployed but **must not** accept live receives until freeze lifts.
>
> Per-shop cutover transaction (watermark + lock): Insert `inventory_truth_cutover (shop_id, generation=1, status=locking, frozen_at=now())` … `SELECT … FOR UPDATE` on that shop’s `inventory_item` and `purchase_record` … Inside the same transaction: backfill A then B. Gap is computed from this locked snapshot. No live receive can commit during freeze.
>
> gap = inventory_item.stock - SUM(quantity_delta for that shop+sku)
>
> Recon must be 0. Timeout is **not** green.
>
> If cutover `status=complete`, retry is no-op. If `locking` after crash: re-enter the same transaction procedure; do not lift freeze until complete or `failed_permanent`.

`TESTS.md` requires opening-gap vs a concurrent receive to finish with `unaccounted_qty = 0`, and a crash during `locking` to retry the same gen:1 keys without a second opening lot.

## Criterion 8 — Holds preserved — PASS

Rollback, receive-first non-rewrite, and fail-closed identity as a separate entry gate are explicit and not contradicted.

Evidence (`INDEX.md` Holds):

> Rollback leaves `InventoryItem` snapshot and `Sale` rows unchanged.
>
> Receive-first slice does not rewrite Sale, Shopify, Watch, payments, or reservations.
>
> Fail-closed shop identity is a **separate** implementation entry gate. This packet does not implement it.

Evidence (`DESIGN.md` Holds): receive-first does not write `Sale` rows or change `finalize_sale`; Shopify dual-write, Watch, payments, and `reserve`/`release` writes are not enabled in this slice; identity is a separate slice.

Evidence (`MIGRATION.md` Rollback): dual-write off; snapshot, `Sale`, and `PurchaseRecord` unchanged.

Evidence (`GATES.md`): this packet does not implement fail-closed identity; that gate is a separate slice required before `implementation_unlock`.

## OVERALL

**READY FOR FREEZE APPROVAL**

All eight criteria PASS. No freeze decision is made here. Executive sponsor owns `FROZEN` or `REJECTED` from this file (14 days; 0 retries of review).
