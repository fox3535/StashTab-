# StashTab Inventory Truth Foundation Contract

**Contract ID:** `STASHTAB-INVENTORY-TRUTH-001`  
**Version:** `1.0.0` → `1.1.0` → `1.2.0` (AMENDMENT-1.2.0 approved; hashes in freezes/FREEZE-1.2.0.json)  
**Status:** `FROZEN`  
**Frozen on:** `2026-08-20`  
**Slice id:** `inventory-truth-foundation`  
**Freeze evidence:** `reviews/FREEZE-CHECK.md` (eight criteria PASS; overall
`READY FOR FREEZE APPROVAL`). Human freeze approved the same day.  
**System of record:** this file. The locked design bodies are the files
listed below. Historical review notes in `reviews/PLANNING-REVIEW.md` and
`reviews/POST-CORRECTION-REVIEW.md` are **not** frozen and must not be
used to weaken this contract.

This freeze does **not** authorize application code, migrations,
dual-write, backfill, authentication work, payments, Watch, commits,
pushes, or deployments.

## 1. Git / worktree reference

- Branch: `feature/card-resolution-notifications`
- Last Git commit: `e5ed96b43234b0816d3320a69ae6fd0ddc2ded22`
  (`Consolidate partner Mimir brain (b798bf0) into StashTab.`)
- Freeze identity is **content hashes**, not that commit. The packet was
  uncommitted in the working tree at freeze.

## 2. Files included in the freeze

Reviewed design bodies (unchanged from the passing freeze check):

| File | SHA-256 |
|---|---|
| `docs/inventory-truth-v1/DESIGN.md` | `1AA1C33EC1ADEFC0FF99DA2D46766448A045AA722798A990D862C20701FDA336` |
| `docs/inventory-truth-v1/MIGRATION.md` | `28806DBFDEEC9A531A68E0CEF85A933D4B0639BCD151E26F7D8E3A81F4C43CC8` |
| `docs/inventory-truth-v1/TESTS.md` | `F40DC45E35497E7047FBEF1A9C371A09D034A8AF2B4ABB135853C00AC43B5ADC` |
| `docs/inventory-truth-v1/reviews/FREEZE-CHECK.md` | `9B59BD7BF892B480C59728C6A13B2010005C5C0E0EBDF2234762074CF12E21F9` |

Freeze envelope (stamped `FROZEN` on 2026-08-20; hashes recorded after
stamp in §2b of this file):

- `docs/inventory-truth-v1/INDEX.md`
- `docs/inventory-truth-v1/GATES.md`
- `docs/inventory-truth-v1/CONTRACT.md` (this file)

Not frozen: `reviews/PLANNING-REVIEW.md`,
`reviews/POST-CORRECTION-REVIEW.md`, any later identity-slice docs.

### 2b. Envelope hashes (after `FROZEN` stamp)

| File | SHA-256 |
|---|---|
| `docs/inventory-truth-v1/INDEX.md` | `A3C2766D8359F170B06A6F9522AC48B695BF4E7F7019969E3D771DA59DE00BC6` |
| `docs/inventory-truth-v1/GATES.md` | `D725D02B2102E40ECEF09B89021333E7DB6FF45E26DA35AD6CA007C6B65EEB42` |

`CONTRACT.md` is this freeze record. Verify it by the frozen date, version
`1.0.0`, and the hashes above — do not treat a later silent edit as
frozen.

## 3. Eight locked design decisions

1. **Quantity equation.** Remaining is `SUM(quantity_delta)` per shop and
   lot (SKU recon uses the same sum). Overlay types, including
   reserve/release, must use `quantity_delta = 0` and never change
   remaining. Receive-first writes only `receive`, `loss`, and reverse of
   those.
2. **Idempotency key.** Canonical form `{source}:{shop_id}:{source_pk}`
   (opening/shrinkage append `:gen:1`). Same string on lot and event.
   Unique `(shop_id, idempotency_key)` per table. Shared by live
   dual-write and backfill. Collision/retry is the five-step rule in
   `DESIGN.md` §2. No `:receive` suffix.
3. **Same-shop keys.** Additive unique `(shop_id, id)` on live
   `inventory_item`, `purchase_record`, and `sale`, then new tables, then
   composite foreign keys. Validate existing `(shop_id, id)` first.
4. **No startup `create_all` for new models.** New lot/event/cutover
   models are imported only by the approved migrator. Acceptance: API
   `init_db` must not create those tables; migrator must.
5. **Closed planning path.**
   `CORRECTION_IN_PROGRESS → READY_FOR_FREEZE_CHECK → FROZEN | REJECTED`.
   No return to open review.
6. **Shrinkage is `loss`.** It must not create a `Sale` row.
7. **Cutover race closed.** Freeze quantity-changing writes first, then
   per-shop watermark lock, backfill inside the lock, then lift freeze
   with dual-write. Retry uses gen:1 keys.
8. **Holds.** Rollback leaves snapshot and `Sale` unchanged. Receive-first
   does not rewrite Sale, Shopify, Watch, payments, or reservations.
   Fail-closed identity is a **separate** implementation entry gate.

## 4. Implementation entry gates

These **block** `inventory-truth-foundation` code, migrations, and
schema apply:

| Gate | Owner | Required evidence |
|---|---|---|
| Fail-closed shop identity (`fail-closed-shop-identity-v1` / `identity-fail-closed`) | Control owner — Identity | Verified JWT + explicit shop membership; production must not trust caller-supplied shop or user headers |
| `implementation_unlock` for `inventory-truth-foundation` | Executive sponsor | This contract `FROZEN`; identity slice `completed`; `TESTS.md` on the PR |
| Schema apply (card-resolution contract §12.8 analogue) | Executive sponsor | Approved migrator plan; `create_all` acceptance check green |

## 5. Specialist / go-live gates (do not block development)

These do **not** block planning or later identity-slice development.
They still block production go-live of the named concern:

- Final COGS method
- Trade-credit / stored-value booking
- Market-data license
- PCI determination
- Stripe/PayPal production configuration
- Production migration approval

## 6. Amendment rule

This contract cannot be silently edited.

A material change requires:

1. A separately versioned proposal under
   `docs/inventory-truth-v1/amendments/` (example:
   `AMENDMENT-1.1.0.md`), stating reason and affected risks.
2. Independent review against the frozen bodies, not against chat.
3. Updated acceptance tests where behavior changes.
4. Named human approval.
5. A new semantic version and a new freeze record. The prior frozen
   hashes remain historical evidence.

Emergency disable of dual-write or freeze of stock overwrites is a
safety action. Re-enablement needs verification and an audit entry.

## 7. Current gate state

`inventory-truth-v1 — FROZEN v1.2.0; SLICE-01 COMPLETED (NOT DEPLOYED);
SLICE-02 COMPLETED (NOT MERGED, NOT DEPLOYED); AMENDMENT-1.2.0 APPROVED;
SLICE-03 PLAN FROZEN, IMPLEMENTATION STILL BLOCKED`

## 8. Amendment 1.1.0 freeze record (2026-08-23)

AMENDMENT-1.1.0 (outbound canonical keys + migration envelope) was
approved by named human vote on 2026-08-23 and applied as the exact diff
in `amendments/AMENDMENT-1.1.0.md`. Resulting contract version: **1.1.0**.

Amended file hashes (SHA-256, stamped after approval):

| File | SHA-256 |
|---|---|
| `DESIGN.md` | `51BAA2522EE3E129467D86F194289B09CA9FAB83465E7AF8CB1E7DA36D346E67` |
| `MIGRATION.md` | `370206CB2B9A01BFC663E5BF5FABEF52E67668568425A37C0193D850B077BD93` |
| `TESTS.md` | `BAACBD912D4FBE5D5FE1D3244A42E309578E74054353072736BF7568AE5CEA50` |
| `amendments/AMENDMENT-1.1.0.md` | `F4B7C17D65E083B7903687ADDC2876B89FCAE1C5A197DA4830B776972FA68483` |

The §2 v1.0.0 freeze record above remains historical evidence for the
prior version and is preserved unchanged. Seven binding owner
interpretations are recorded in `amendments/AMENDMENT-1.1.0.md` §17.
Independent review evidence: `reviews/SLICE-02-PLANNING-REVIEWS.md`.

## 9. Amendment 1.2.0 freeze record

Resulting contract version: **1.2.0**.
Approved amendment: `AMENDMENT-1.2.0`.
Freeze manifest: `docs/inventory-truth-v1/freezes/FREEZE-1.2.0.json`.
Byte hashes, algorithm, freeze timestamp, and file list live only in
that manifest. This file does not store its own SHA-256.
The §2 v1.0.0 and §8 v1.1.0 records remain unchanged.
