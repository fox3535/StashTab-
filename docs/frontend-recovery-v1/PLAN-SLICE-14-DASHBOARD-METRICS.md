# Plan — frontend-recovery-v1 / slice-14 dashboard metrics

**Status:** PLAN FINAL — decisions D1–D4 recorded 2026-10-20 (§6). Ready to implement; no code yet.
**Pinned to:** `feature/resticker-queue` `117495b` (stack: PR #44 → slice-12 → slice-13).
**Author/date:** partner builder session, 2026-10-20.
**Live-operation gates:** none requested. F2 / Gate 2 remain HELD.

## 1. Outcome

Replace the dashboard sentence "Revenue, inventory totals, alerts, and
operational metrics are not shown until their data slices are accepted"
with a small row of read-only stat tiles fed by the existing
authenticated `GET /api/v1/admin/dashboard` contract. Ready and Deferred
tool cards stay exactly as they are.

## 2. Evidence (verified at `117495b`)

### 2.1 The existing contract

`services/api/app/routers/admin.py` `dashboard_kpis` (shop-scoped via
`get_shop_context`; any member role, no owner check) returns:

| Field | What it actually computes | Notes |
|---|---|---|
| `inventory_count` | number of inventory **rows (SKUs)** with `stock > 0` | not units |
| `inventory_value` | `SUM(price × stock)` over **all** rows of the shop | current sell price, not cost; no `stock > 0` filter |
| `staging_count` | rows in `staging_item` | staging/intake is a deferred feature |
| `pending_sync` | `sync_outbox` rows with `sync_status = 'pending'` | Shopify sync is OFF |
| `total_revenue` | `SUM(sale.net_revenue)`, **all time** | net of card fees; trade-paid sales contribute 0 (`pricing.calculate_net_revenue`) |
| `sale_count` | `COUNT(sale)`, all time | includes online (`transaction_type="online"`) sales |
| `paperweight_units` | `count_paperweight_units` | same number as slice-12 report header |

Internal variable is named `today_sales` but there is **no date filter**;
the returned field names (`total_revenue`, `sale_count`) are accurate.
No backend test covers this endpoint today.

### 2.2 Recorded decisions this slice must respect

- **Slice-02** removed the old KPI fetch and pinned
  `scripts/test_dashboard_cleanup.mjs` "dashboard never invents metrics or
  fetches KPIs" (no `adminRequest`, no `total_revenue`, no
  `inventory_value`, keeps "never invents numbers"). Rationale: *invented*
  numbers. The slice-02 page copy promised "Metrics arrive with their own
  slices" — this is that slice, so amending the test is intended, not a
  weakening; the honesty invariant is restated, not dropped (§5).
- **Slice-08** deliberately hid `profit`, `trade_in_value`, `net_revenue`
  from Sales History as "booth-facing margin and internals". Showing
  revenue on the dashboard therefore needs an explicit owner decision (D2).
- **vendor-core** test keeps "This page never invents numbers." and the
  exact dashboard link allowlist.
- Roles are `owner` | `staff` (`models/shop.py`). The endpoint does not
  check role, so hiding a tile in the UI is cosmetic, not access control.

### 2.3 Partner parity (`vendor/mimir-partner/main.py` `MainDashboard`)

Partner tiles: Portfolio value (`price × stock`), Active stock **units**,
Operational margin %, Paperweight, Trade credit 30d, Cash profit 30d.
StashTab's endpoint matches portfolio value and paperweight; differs on
stock (SKUs vs units); has no margin or 30-day windows. This slice does
not add them (would need backend changes and money decisions; see §7).

### 2.4 Design system

`UI_DESIGN_SYSTEM.md` / `OPEN_DESIGN_HANDOFF.md`: dashboard stats are
large (`text-4xl/5xl`), bold, white, `font-display`; cards `bg-gunmetal`
+ `border-border` + `rounded-xl`; labels small uppercase mono `text-steel`;
ember = warning (paperweight), emerald = profit. Stat tiles, not charts:
there is no time series to plot. Values use proportional figures at
display size; no sparklines or deltas (no history in the contract).

## 3. Proposed tiles (pending D1–D3)

| Tile | Source | Label / honesty copy |
|---|---|---|
| In-stock items | `inventory_count` | "SKUs with stock > 0" |
| Inventory value | `inventory_value` | "At current sell price, not cost" |
| Stagnant units | `paperweight_units` | ember when > 0; links to `/admin/paperweight` |
| Sales recorded | `sale_count` | "All time" — **only if D2 allows sales tiles** |
| Net revenue | `total_revenue` | "All time, after card fees; trade-paid sales add $0" — **only if D2 = show** |

Never shown: `pending_sync` (Shopify off), `staging_count` unless D3 = show.

## 4. Behaviour

- New `mimirApi.dashboardMetrics` wrapper (GET only) + `DashboardMetrics`
  type; pure helpers in new `lib/dashboard-metrics.ts` (compact number and
  money formatting; missing/non-numeric → "—").
- Same guards as slices 06–13: membership shop context, `AbortController`,
  epoch, `shouldApplyShopResult`, clear on shop switch, `reportApiError`.
- States: loading skeleton tiles ("…"), error banner with tiles showing
  "—" (never 0), honest zero for an empty shop ("0" is real data here),
  `aria-live` summary, `role="status"`.
- Ready/Deferred cards render regardless of metrics state; a metrics
  failure never hides navigation.
- Layout: 2 columns on phone, 3–5 on desktop; no horizontal overflow;
  touch targets ≥ 44px on the Stagnant tile link.
- No polling; fetch on load and on shop switch only.

## 5. Tests

**Backend (new `services/api/tests/test_dashboard_metrics.py`, test-only):**
pin each field's semantics on SQLite fixtures — SKU count excludes
stock 0; value = Σ price × stock; revenue = Σ net_revenue all time (trade
sale contributes 0); counts are shop-isolated; `paperweight_units` equals
the slice-12 report `units`; response keys exactly as §2.1.

**Frontend (new `scripts/test_dashboard_metrics.mjs`, `test:slice14`):**
helper mirrors; wrapper is GET-only; page renders only contract fields;
never references `pending_sync` (and `staging_count` / `total_revenue` /
`sale_count` per decisions); error shows "—" not 0; guards present;
ready/deferred cards and link allowlist unchanged.

**Amended existing tests (intentional, listed in the PR):**
- `test_dashboard_cleanup.mjs` "never invents metrics or fetches KPIs" →
  "metrics come only from the accepted GET contract": still forbids
  `adminRequest`, invented values, and `pending_sync`; still requires
  "never invents numbers".
- `test_vendor_core_batch.mjs` unchanged (phrase kept, allowlist unchanged).

**Checks:** all Node suites, `tsc --noEmit`, non-PG pytest, and a local
visual check with FIXTURE data (desktop + phone), as for slices 12–13.

## 6. Owner decisions needed before implementation

- **D1 — Tile set.** Recommended: In-stock items, Inventory value,
  Stagnant units (inventory-only, no money from sales).
- **D2 — Sales money.** (a) *Recommended:* omit `total_revenue` and
  `sale_count` this slice; (b) show to every member (matches what the API
  already returns to staff; reverses the slice-08 caution);
  (c) owner-only in the UI — cosmetic only; true restriction needs a
  backend role check (auth change → separate approval by Chris).
- **D3 — Staging count.** Recommended: omit (staging/intake deferred; the
  number is not actionable yet).
- **D4 — Units vs SKUs.** Recommended: show SKUs as the contract returns,
  labelled clearly; adding a units field is a backend change for a later
  slice.

### Recorded answers (partner, 2026-10-20)

- **D1:** In-stock items, Inventory value, Stagnant units — confirmed.
- **D2:** (a) omit `total_revenue` and `sale_count` this slice. Who may see
  sales money, and whether the API should restrict it to owners, goes to
  Chris as a separate decision.
- **D3:** omit `staging_count`.
- **D4:** show SKUs as returned, labelled "SKUs with stock > 0"; no backend change.

Resulting build: exactly three tiles (§3 rows 1–3). The page and tests
must not reference `total_revenue`, `sale_count`, `staging_count`, or
`pending_sync`. Backend tests still pin all seven fields so a later money
slice starts from verified semantics.

## 7. Out of scope

Margin %, 30-day windows, trade-credit totals, units total, charts,
deltas, exports, role-based API restriction, Shopify sync status,
any write, any backend logic change, any staging/Neon/deploy action.

## 8. Risks

| Risk | Mitigation |
|---|---|
| Value read as profit or cost | Label "at current sell price, not cost" |
| Revenue read as gross sales | Omit (D2a) or label "after card fees; trade-paid sales add $0" |
| Float money rounding | 2-decimal display; exact-money migration is a later financial-ops slice |
| Staff seeing money | D2; real fix is backend role check (separate gate) |
| Metrics error blanks dashboard | Tiles fail independently of navigation cards |

## 9. Exit

Slice is done when the D1–D4 choices are implemented, all checks in §5
pass, the owner has seen it locally with FIXTURE data, and it is pushed
as a draft PR stacked on slice-13. Merge and deploy remain separate approvals.
