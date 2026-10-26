# Plan — frontend-recovery-v1 / slice-15 read-only staging queue

**Status:** PLAN FINAL — decisions D1–D3 recorded 2026-10-26 (§6). Ready to implement; no code yet.
**Pinned to:** `feature/dashboard-metrics` `082a4b9`
(stack: PR #44 → slice-12 → slice-13 → slice-14).
**Author/date:** partner builder session, 2026-10-26.
**Live-operation gates:** none requested. F2 / Gate 2 remain HELD.

## 1. Outcome

Unlock `/admin/staging` as a read-only list of items held in staging
(identified cards waiting to enter inventory), so a vendor can see what is
queued. Every staging action stays locked and is not wired at all.

## 2. Evidence (verified at `082a4b9`)

### 2.1 The existing read contract

`services/api/app/routers/admin.py` `list_staging` — `GET /admin/staging`,
shop-scoped via `get_shop_context`, any member role:

- returns `{ items: [...] }`, the **100 newest** rows by `id` desc; no total,
  no pagination;
- each row: `id, name, sku, market_price, suggested_price, image_url`
  (= `image_path`), `quantity, set_name, sequence_number`;
- **not returned** although stored: `condition, variant, card_type, game,
  needs_review, cost_basis, barcode_path`.
- No backend test covers `GET /admin/staging` today.

### 2.2 Where rows and numbers come from

- Only `logic/intake.py add_to_staging` creates rows (intake is deferred).
  Identical identity (name, set, number, variant, **condition**, card type)
  merges by adding quantity — so two rows for the same card differ only by
  fields the GET does not return.
- `market_price`: from the card data provider (Pokémon TCG API prices are
  USD converted with the fixed `usd_to_cad_rate` 1.43) or a manual entry.
  `suggested_price` = `suggested_price_for_shop(market_price)`.
  `cost_basis` = market × shop buy rate (money; not returned, not shown).
- Images: `persist_card_image` stores `/static/scraped_thumbnails/{sku}.png`
  or falls back to the provider URL. The accepted `CardThumbnail`
  (POS Find, item detail) already resolves both and falls back to a text
  tile on error; `next.config.ts` allows only the existing image hosts.

### 2.3 Why commit must stay locked

`commit_staging_item` → `_truth_dual_write_staging_commit` →
`inventory_truth.record_staging_commit_receive`: committing staging **is
the inventory-truth receive path** governed by the frozen
inventory-truth contract and the held F2 cutover. This slice adds no
wrapper for commit, commit-all, apply-trades, refetch, or delete.

### 2.4 Legacy page and partner parity

The current locked `app/admin/staging/page.tsx` uses legacy `adminApi`,
swallows errors into an empty list, and exposes commit / commit-all /
refetch / delete / apply-trades buttons. Partner `StagingDockFrame` adds
clear, apply-trade-values, and a name/set/number filter. This slice keeps
only the read view; a local filter is out of scope (see §7).

## 3. Proposed screen

| Column (desktop) / line (phone card) | Source |
|---|---|
| Thumbnail | `image_url` via `CardThumbnail` (D1) |
| Item: name · SKU · set · #number | `name, sku, set_name, sequence_number` |
| Condition / variant | **only if D2 = (b)** |
| Qty | `quantity` |
| Market price | `market_price` — caption "from card data; not your price" |
| Suggested sell price | `suggested_price` |

Header: count of rows shown. Notice: "Showing N newest staged items" and,
at 100, "the API returns at most the 100 newest; more may be staged" (D3).
Subtitle states that committing to inventory, editing, removing, and
applying trades are not ready.

## 4. Behaviour

- New `mimirApi.stagingQueue` (GET only) + `StagingItem` type with exactly
  the returned fields; helpers in new `lib/staging-queue.ts` (money "—" for
  missing, `set · #number` line, cap notice).
- Same guards as slices 06–14: membership shop context, abort + epoch,
  clear on shop switch, `reportApiError`, `aria-live`, `role="status"`.
- Honest states: loading block; error banner (never an empty list on
  error, unlike the legacy page); empty "Nothing is waiting in staging for
  this shop. This is an empty result, not a failed write."
- Desktop table, phone cards, no horizontal overflow.
- Route gate: remove `/admin/staging`; Intake, Import, Settings, Shopify,
  Pulls, Stats stay locked. Sidebar: unlock "Staging". Dashboard: add a
  "Staging Queue" ready card (dashboard link allowlists extended as in 12–13).

## 5. Tests

**Backend (new `services/api/tests/test_staging_queue.py`, test-only unless D2b):**
newest-first order; 100 cap; shop isolation; exact response keys;
GET writes nothing (quantities/prices unchanged); merge-by-identity
produces one row with summed quantity (pins the §2.2 behaviour the UI explains).

**Frontend (new `scripts/test_staging_queue.mjs`, `test:slice15`):**
helper mirrors; wrapper GET-only and no `commit`/`refetch`/`apply-trades`/
DELETE wrappers in `mimir-api`; page renders only contract fields; never
shows `cost_basis`; no buttons/onClick/toast/adminApi; guards; empty/error
honesty; cap notice; gate/sidebar/dashboard entries; other routes still locked.

**Amended (intentional):** dashboard link allowlists in slices 09/10/11/
vendor-core and the slice-12/13 "others stay locked" lists drop
`/admin/staging`.

**Checks:** all Node suites, `tsc --noEmit`, non-PG pytest, local visual
check with FIXTURE staging rows (desktop + phone).

## 6. Owner decisions needed

- **D1 — Thumbnails.** (a) *Recommended:* show via the accepted
  `CardThumbnail` (no new image hosts; text tile on failure);
  (b) text only.
- **D2 — Condition and variant.** The GET omits them, so two staged copies
  of one card in different conditions would look identical.
  (a) ship without them and say so; (b) *Recommended:* additive backend
  change — also return `condition`, `variant`, `card_type`, `needs_review`
  from `GET /admin/staging` (read-only, no schema change, covered by the
  new backend test), and show condition/variant. `cost_basis` stays out
  either way.
- **D3 — Cap disclosure.** (a) *Recommended:* disclose the 100-newest cap
  in the notice only; (b) also fetch the exact total from
  `GET /admin/dashboard` `staging_count` (second request).

### Recorded answers (partner, 2026-10-26)

- **D1:** (a) thumbnails via the accepted `CardThumbnail`.
- **D2:** (b) additive read-only backend change: `GET /admin/staging` also
  returns `condition`, `variant`, `card_type`, `needs_review`; the screen
  shows condition and variant. `cost_basis`, `barcode_path`, `ocr_metadata`
  stay out. No schema change, no write path touched; the new backend test
  pins the new keys and that the route still writes nothing.
- **D3:** (a) cap disclosed in the notice only; one request.

## 7. Out of scope

Commit / commit-all / apply-trades / refetch / delete / clear; editing;
intake; local search or filter; pagination; cost basis or margin; label
printing; currency relabelling (app-wide question, see §8); any
staging/Neon/deploy action.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Read view mistaken for a working commit flow | No action controls; subtitle says commit is not ready; tests ban wrappers |
| Identical-looking rows (condition hidden) | D2b, or explicit note under D2a |
| Market price read as the shop's price | Caption "from card data; not your price"; suggested price labelled separately |
| Currency: provider USD converted at fixed 1.43, shown as "$" | Same "$" convention as every accepted screen; raise app-wide currency labelling with Chris separately |
| External image requests | Only the already-allowed hosts via the accepted component |

## 9. Exit

Done when D1–D3 are implemented, §5 checks pass, the owner has seen it
locally with FIXTURE staging rows, and it is pushed as a branch stacked on
slice-14. Merge and deploy remain separate approvals.
