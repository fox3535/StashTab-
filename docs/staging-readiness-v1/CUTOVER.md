# Cutover and reconciliation (staging rehearsal)

Follow frozen `docs/inventory-truth-v1/MIGRATION.md` order. Do not invent a faster path.

Slice 0 does **not** cut over. Receive/POS/adjust stay `503 FEATURE_NOT_READY` until a later named unlock.

## Freeze (per synthetic shop)

While frozen, reject: staging commit, trade receive, POS finalize, Shopify pull/push, admin PATCH stock, CSV stock overwrite. Price-only PATCH may remain if it cannot touch quantity/cost.

## Gen-1 cutover transaction (locked)

1. Insert `inventory_truth_cutover` generation 1 `locking`, or fail if complete gen 1 exists.
2. `SELECT … FOR UPDATE` on that shop’s items and purchase records used in this generation.
3. Backfill purchase records (lot + receive, canonical keys).
4. Opening gap: snapshot stock minus sum of event deltas. Positive → opening receive; negative → shrinkage **loss** (not a Sale); zero → nothing.
5. Mark cutover `complete`. Commit.
6. Enable receive dual-write and lift freeze for intake/trade/POS **in the same approved step**. PATCH/CSV stock overwrite stay frozen until adjust slice policy says otherwise.

## Dual-write checks

- Receive, outbound, adjust writers share `inventory_event` and stay shop-scoped.
- Snapshot `inventory_item.stock` remains operational quantity until a later production cutover decision.
- Notification recover **reads** open `inventory_exception`; ack/resolve **must not** close those exceptions.

## Zero-mismatch recon

```
event_remaining(sku) = SUM(quantity_delta) for shop+sku
mismatch if event_remaining != inventory_item.stock
```

Timeout is **not** green. Any mismatch → abort cutover lift.

## Notification checks (only after schema exists; flag still off)

- Tables exist, routes still 404 if flag off.
- No recover/process on worker.
- When a **later** slice turns the flag on: recover creates notification rows from open exceptions without changing exception status; mocked transport only.

## Abort

- Any production Shopify or production DB write.
- Recon ≠ 0.
- Cross-shop leak.
- Migrator created a role on a shared cluster.
- Identity bypass on.
- Notification flag or real VAPID on during first slices.

## Safe rollback state

Snapshot and `sale`/`purchase_record` unchanged. Truth tables may remain. Dual-write not accepting live receives. Notification flag off. Worker stopped or auto-sync off.
