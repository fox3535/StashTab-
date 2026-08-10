# Mimir SaaS — Master Plan

> **How to use this file:** Cursor agents should read this before implementing. Chat is for decisions; this file is the source of truth for what to build next.
>
> **Last updated:** Phase 1–6 complete (StashTab launch-ready). Docs cleaned for repo.
>
> **Partner repo (reference only, do not push here):** `https://github.com/OdinFury-D/Mimir.git`  
> **Local brain snapshot (Python only, no images):** `D:\Users\Desktop\Cursor Projects\Mimir-brain`

---

## Architecture

```text
Phone / Browser
      ↓
Next.js (TypeScript)     ← UI: mobile POS + admin + landing
      ↓
FastAPI (Python)         ← Brain: port logic from Mimir Card Shop App
      ↓
PostgreSQL               ← Inventory, sales, sync outbox (multi-tenant via shop_id)

Clerk = auth + billing shell
Convex = users + subscription tracking (from starter kit)
```

**Do NOT rewrite business logic in TypeScript.** Port Python from:
`Mimir/Card Shop App/card_shop_app/`

---

## Phase Status

| Phase | Name | Status |
|-------|------|--------|
| 0 | Foundation (scaffold, DB, dev env) | ✅ DONE |
| 1 | Mobile POS (sell at shows) | ✅ DONE |
| 2 | Shopify cloud sync | ✅ DONE |
| 3 | Admin dashboard (intake, inventory) | ✅ DONE |
| 4 | Reconciliation + reports | ✅ DONE |
| 5 | Show mode + P&L | ✅ DONE |
| 6 | SaaS launch (billing tiers, deploy) | ✅ DONE |
| 7 | OCR upload, native app | ⏳ Post-launch |

---

## Phase 2 — Shopify Cloud Sync ✅

- [x] Background worker (`worker.py`)
- [x] Full `_process_sync_outbox()` with product create/update
- [x] `_pull_shopify_orders()` — inbound orders
- [x] Per-shop Shopify credentials
- [x] Online sale toast (polling)
- [x] Admin: Connect Shopify settings page
- [x] Verify Shopify consistency

---

## Phase 3 — Admin Dashboard ✅

| Mimir screen | Admin route | Status |
|---|---|---|
| ManualIntakeFrame | `/admin/intake` | ✅ singles + sealed |
| StagingDockFrame | `/admin/staging` | ✅ + apply trade values |
| InventoryManagerFrame | `/admin/inventory` | ✅ inline edit |
| ReviewSyncFrame | `/admin/shopify/review` | ✅ |
| ShopifySyncFrame | `/admin/shopify/sync` | ✅ |
| SettingsFrame | `/admin/settings` | ✅ |
| import_engine | `/admin/import` | ✅ |
| Resticker queue | `/admin/resticker` | ✅ |

---

## Phase 6 — SaaS Launch ✅

- [x] Clerk Billing tiers (Free / Pro) — admin gated via `<Protect>`
- [x] Onboarding: sign up → create shop → connect Shopify
- [x] Team invites
- [x] Deploy docs: `DEPLOY.md`, `Dockerfile`, `railway.toml`
- [x] StashTab landing rebrand
- [x] PWA icons (192/512 PNG)
- [ ] Custom domain — ops step at deploy time

---

## Feature Parity Checklist

- [x] Manual intake (single + sealed)
- [x] Staging dock + batch commit
- [x] Apply trade values to staging
- [x] Full inventory vault (filters, inline edit)
- [x] Live POS / mobile checkout
- [x] Placeholder trades
- [x] Cash + trade settlement
- [x] Sold online pull list
- [x] Shopify sync outbox + force sync
- [x] Verify Shopify consistency
- [x] Review & sync staging to Shopify
- [x] Collectr CSV reconciliation
- [x] CSV import
- [x] Settings (buy %, trade %, markup, rounding, shipping rules)
- [x] Dashboard KPIs + paperweight alert
- [x] Trade history + export
- [x] Show price capture
- [x] Label generation (QR/barcode)
- [x] Updated cards / needs restickering
- [x] Pokemon TCG API fetch on intake
- [x] Persistent SKU reuse across acquisitions
- [x] Local image repository (`/static/scraped_thumbnails`)

See [FEATURE_PARITY.md](./FEATURE_PARITY.md) for the full partner-feature matrix.
---

## Local Dev

```powershell
docker compose up -d
cd services/api; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8001
npm run dev -- -p 3001
```

**URLs:** Landing `:3001` · POS `:3001/pos` · API docs `:8001/docs`

---

## Agent Instructions

1. Read this file first. Phase 7 (OCR, native app) is post-launch only.
2. Port Python logic from Mimir repo — don't rewrite in TypeScript.
3. Multi-tenant: every query must filter by `shop_id`.
4. Do not push to git unless user explicitly asks.
