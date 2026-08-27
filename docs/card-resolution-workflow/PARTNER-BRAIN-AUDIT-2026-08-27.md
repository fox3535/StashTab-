# Partner Python brain audit (read-only)

**Date:** 2026-08-27  
**StashTab pin:** `main` `d49eca9fc31298847bd07abf42347ab691b4f974`  
**Vendored snapshot:** `vendor/mimir-partner/` (README: GitHub `b798bf0`, 2026-08-12)  
**Upstream:** `https://github.com/OdinFury-D/Mimir`  
**Upstream default branch:** `main`  
**Upstream HEAD:** `df280478f09a179fcffb1842d89bcf8f1d86e03b` (2026-08-19, subject “Batch commit 46 of 46”)  
**Access:** `git ls-remote` / sparse clone succeeded with existing GitHub git auth. `gh` CLI not installed. Public HTTPS page returned 404 (private). Credentials were not printed.  
**Temp clone (outside repo):** `%TEMP%\mimir-upstream-audit` (sparse; no card images, no sqlite, no `.env`)  
**Vendor tree was not modified.** Frozen card-resolution contract was not modified. No APIs or TCGCSV downloads were invoked. No code was executed.

Scoring-weight freeze was paused for this audit. **D-031** keeps `b798bf0`
and treats `df280478f09a179fcffb1842d89bcf8f1d86e03b` as reference only.
Scoring-policy work resumed; not frozen.

## License and copy rights

No `LICENSE`, `COPYING`, or `NOTICE` file exists in upstream HEAD or in the vendored snapshot. The GitHub project is not publicly fetchable. No recorded partner grant to copy/modify into StashTab appears in this audit.

**Treatment:** reference-only. Do not merge, overwrite `vendor/mimir-partner/`, or vendor new trees until the owner records written permission or a license.

## Snapshot vs upstream (overlapping POS files)

Mapped `vendor/mimir-partner/<file>` ↔ `Card Shop App/card_shop_app/<file>`.

**Unchanged:** `config.py`, `database.py`, `logic.py`, `ocr_engine.py`, `import_engine.py`, `graded_wizard_module.py`, `find_fuzzy_duplicates.py`, `migrate_db.py`, `migrate_tcg_game.py`, `cleanup_shopify_duplicates.py`, `sanitize_inventory_numbers.py`, `revert_inventory_numbers.py`, `requirements.txt`.

**Changed (small):**

- `api_client.py` — Pokemon TCG API result now formats collector number as `number/printedTotal` when missing a slash.
- `core.py` `CoreManager.process_card` — copies that official number into parsed sequence when `match_verified`.
- `core.py` Shopify consistency — paused stock uses `max(0, stock - paused_stock)`.
- `reconciliation_engine.py` — Collectr CSV recon; still fuzzy set match `partial_ratio >= 70`.
- `web_checkout_module.py` — large checkout/mobile/telemetry change, not identity resolution.
- `main.py` — small UI/sync diffs.

**New upstream trees not in the vendor snapshot:** `Card Shop App/image_db_manager/` (`justtcg_sync.py`, `tcgcsv_sync.py`, `api_fetcher.py`, `pokellector_scraper.py`, `auto_sync_worker.py`, `db_handler.py`, …). Separate SQLite catalog/image/price DB, not the POS `inventory_item` path.

## Matching / resolution behavior

Upstream identity for intake is still Pokemon TCG API + RapidFuzz, not a contract scorer:

- `core.py` `PokemonTCGAPIClient.fetch_card_data` — `fuzz.WRatio(local_name, api_name) >= 80` ⇒ `match_verified`.
- `core.py` `CoreManager.process_card` — OCR name confidence `< 70` ⇒ `needs_review` but still builds a staging payload.
- `ocr_engine.py` `fuzzy_correct_set_name` — WRatio ≥ 60 rewrites set names.
- `tcgcsv_sync.py` `match_set_name` — WRatio ≥ 85 **renames** local sets to TCGCSV names.
- `tcgcsv_sync.py` card match — WRatio ≥ 90 (or substring) then **UPDATE** catalog rows including `card_name` / `card_number` / `market_price`.
- `justtcg_sync.py` `sync_set` — substring “fuzzy” set match, then upserts variant prices.

No explicit abstention terminal. Weak evidence still proceeds to staging. No `shop_id`.

**Games:** POS intake remains Pokemon-centric (Pokemon TCG API). TCGCSV `sync_all` pulls TCGPlayer categories **3 = Pokemon English** and **68 = One Piece English**. JustTCG `game_map` is Pokemon + One Piece. TCGdex fetcher: Pokemon EN/JP/CN. Not a full multi-game contract catalog.

## TCGCSV

- **Files:** `image_db_manager/tcgcsv_sync.py` (`fetch_csv`, `get_groups`, `get_products_and_prices`, `sync_category`, `sync_all`, `should_sync`, `match_set_name`).
- **Source:** `https://tcgcsv.com/tcgplayer/{category}/{group}/ProductsAndPrices.csv` and `Groups.csv`; freshness via `https://tcgcsv.com/last-updated.txt`.
- **Cache:** local `tcgcsv_last_sync.txt` timestamp; 100ms delay per fetch; 0.5s between groups.
- **Writes:** SQLite `Sets` / `Images` (catalog), including inserts of unmatched products and price/image URL updates. Not POS inventory promotion, but it **does** mutate the catalog DB automatically.
- **Licensing:** **not documented in-repo.** TCGCSV redistributes TCGPlayer public CSVs; commercial-use terms were **not** fetched and are **not** recorded. Do not ingest until the owner confirms allowed use, attribution, and refresh policy.
- **Provenance/freshness:** remote last-updated stamp only; no hash of CSV rows; fuzzy rename can overwrite local set identity.

## JustTCG

- **File:** `image_db_manager/justtcg_sync.py` (`_get_api_key`, `sync_set`, `sync_all_active_sets`).
- **Trigger:** desktop “sync set/all” and `auto_sync_worker.py` (hourly-style loop when enabled). Not a low-confidence identity fallback.
- **Auth:** reads `JUSTTCG_API_KEY=` from a sibling `.env` (not present in this sparse clone). Header `x-api-key`.
- **Requests:** `GET /v1/sets?game=…&limit=500` then paginated `GET /v1/cards?set=…&limit=20&offset=…` with **6.5s** sleep; **429 → sleep 60s and retry** unbounded `continue`.
- **Batching:** page size 20; no request budget or credit ledger.
- **Use:** **pricing + printing variants** (Near Mint / Sealed) and **set/card numbers** on the **image/catalog** SQLite DB. It does **not** resolve POS `inventory_item` identity. Shop intake identity is still Pokemon TCG API + RapidFuzz in `core.py`. Also rewrites local catalog numbers (`upgrade_card_number`).
- **Failure:** print + return; does not abstain a shop intake (no intake object).
- **This audit did not call JustTCG.** StashTab must keep JustTCG **disabled**.

## AI / models

No OpenAI/Anthropic/LLM client found. “AI” here is OCR (EasyOCR/Tesseract) plus RapidFuzz. Advisory-agent rules in StashTab still apply: OCR/fuzzy is not verified identity.

## Database writes / auto promotion

- Unchanged `logic.py` still writes `staging_item` and can commit to `inventory_item` (single-shop).
- New image-db syncs auto-write catalog/prices/images in SQLite.
- Checkout/search APIs in `web_checkout_module.py` query `InventoryItem` with **no shop scope**.
- Telemetry: `POST /api/telemetry` logs browser crash text locally (not a third-party analytics SDK).

## Secrets / network

- JustTCG key from `.env`.
- Shopify from `SHOPIFY_API_KEY` env in `services/shopify_client.py`.
- Network: Pokemon TCG API, JustTCG, tcgcsv.com, api.tcgdex.net, Pokellector scrape, Shopify, eBay (graded wizard), image CDNs.
- No StashTab shop membership or Clerk.

## Tests

Ad-hoc scripts (`test_unseen.py` **would** call `tcgcsv_sync.sync_category` if run). No pytest identity/abstention suite. **Not executed.**

## Conflicts with StashTab frozen contract / shop architecture

| Upstream behavior | Conflict |
|---|---|
| Fuzzy ≥80 `match_verified` | Contract: unique ≥0.95 + margin; name is not a unique key |
| TCGCSV/JustTCG auto catalog writes | Shop-scoped identity, human review, idempotency, inventory-write gates |
| JustTCG used as bulk price/variant sync | Must be bounded unresolved fallback only; budgets; abstain on failure |
| Price fields mixed into identity merge (`USE_API_PRICE`) | Identity vs price confidence must stay separate |
| No `shop_id` | Multi-tenant fail-closed |
| Unbounded 429 retry | Budget/liveness |
| Missing license | Cannot copy into `vendor/` without owner grant |

## Source-to-target recommendations

| Upstream | SHA | StashTab target | Preserve | Adapt | Conflict | Parity test | Rec |
|---|---|---|---|---|---|---|---|
| `api_client.py` `_extract_card_result` printedTotal | `df280478…` | `services/api/app/logic/pokemon_api.py` (later; not this slice) | Collector number `n/total` | Shop-scope; never treat as verified identity | Network identity ≠ accept | Number format fixture | **adapt** later |
| `core.py` copy official number | same | intake/resolution scorer (future) | Prefer structured number when verified | Only after local unique accept | `match_verified` still fuzzy | Sequence override test | **adapt** later |
| `core.py` paused_stock | same | inventory paused stock (already on StashTab model) | Pause math | Keep StashTab shop_id + cutover gates | None if not replacing FastAPI | Pause listing qty | **defer** |
| `justtcg_sync.py` `sync_set` | same | future JustTCG adapter (disabled) | Pagination, variant Near Mint, 429 handling idea | Hard budget, cache, shop_id, abstain, no .env file scrape, no unbounded retry, no auto number rewrite | Bulk sync + fuzzy set match; credits | Mock 429/budget/abstain; **no live credits** | **reject** as-is; **adapt** later as fallback-only |
| `tcgcsv_sync.py` `sync_all` / `match_set_name` | same | local candidate evidence store (not inventory) | Structured set/number/name/price CSV | License check; no fuzzy rename of canonical ids; shop-safe catalog; freshness hash | Fuzzy ≥85/90 as identity; undocumented commercial terms | License recorded; no auto-accept from CSV | **defer** until license + catalog design |
| `api_fetcher.py` TCGdex | same | optional image/catalog | JP/CN set fetch | Not identity authority | Extra network | None now | **defer** |
| `pokellector_scraper.py` | same | none | — | Scraping | ToS/network | — | **reject** |
| `ocr_engine.py` (unchanged vs vendor) | `b798bf0` | future OCR evidence | Field extraction | Confidence as evidence only | Fuzzy set rewrite ≥60 | Abstain on low OCR | **defer** (intake slice has no OCR) |
| `logic.py` staging/commit (unchanged) | `b798bf0` | `logic/intake.py` | Hold-then-commit order | Must remain FEATURE_NOT_READY / cutover | Auto inventory write | D-029 unused intake | **reject** for this slice |
| `web_checkout_module.py` | `df280478…` | existing search/checkout | — | Do not replace FastAPI search | No shop_id; telemetry | — | **reject** replacing StashTab |
| `reconciliation_engine.py` | same | later recon | Collectr CSV ideas | Shop_id; no fuzzy 70 as identity | Fuzzy set match | — | **defer** |

## Terminal recommendation

**Selectively port named functions later. Keep the current `vendor/mimir-partner/` snapshot for now.**

Reasons:

1. No license / copy grant; repo is private.
2. Most POS brain files are byte-identical to `b798bf0`.
3. New matching lives in `image_db_manager/` and conflicts with frozen identity rules if copied wholesale.
4. JustTCG/TCGCSV must not run in StashTab until explicit unlocks; this audit did not and must not call them.

Do **not** update the vendor snapshot in this action.

### Bounded snapshot-update plan (only if later approved)

1. Partner records a license or written permission to snapshot Python/docs.
2. Sparse copy **only** `*.py` / `*.md` / `*.txt` / `requirements.txt` from `card_shop_app/` and optionally `image_db_manager/*.py`.
3. Exclude `card_images/`, `static/`, `*.db*`, `.env`, secrets, `__pycache__`.
4. Pin README to `df280478f09a179fcffb1842d89bcf8f1d86e03b`.
5. Diff review: no secrets; no default JustTCG/TCGCSV auto-sync in StashTab runtime.
6. Separate PR; no implementation of card-resolution in that PR.

## Review (one pass)

Architecture: new catalog sync is a second brain; FastAPI stays authority.  
Integrity: fuzzy-as-verified and auto catalog writes conflict.  
Security: `.env` key loader and unscoped checkout search.  
Adversarial: substring JustTCG set match; TCGCSV rename.  
AI quality: no LLM; OCR/fuzzy still not identity.  
Liveness: unbounded 429 retry.

**Correction:** distinguish POS `logic.py` (unchanged, still unsafe to copy) from `image_db_manager` (new, catalog/price). Recommendation stays **selective later port**, not snapshot replace, until license is recorded.
