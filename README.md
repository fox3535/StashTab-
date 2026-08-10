# StashTab

Multi-tenant SaaS for TCG card shops — mobile show-floor POS, admin back office, and Shopify sync.

**Product name:** StashTab · **Internal codename:** Mimir SaaS

## Architecture

```text
Phone / Browser
      ↓
Next.js 15 (TypeScript + shadcn/ui + Tailwind)   ← UI
      ↓
FastAPI (Python) in services/api/                ← business logic
      ↓
PostgreSQL (all tenant data scoped by shop_id)

Clerk  = auth + billing
Convex = users + subscription tracking only (not inventory)
```

Business rules are ported from the partner desktop Card Shop App into Python. Do not rewrite inventory logic in TypeScript.

## Features

- Mobile POS (`/pos`) — sell, cash/trade/card checkout, pull online orders, show mode
- Admin (`/admin/*`) — intake, staging, inventory, Shopify sync, Collectr reconciliation, reports
- Shopify cloud sync — outbox worker, pull orders, verify catalog
- Onboarding, team invites, Clerk Free/Pro billing gate
- PWA-ready for show-floor use

## Stack

| Layer | Tech |
|-------|------|
| UI | Next.js 15, TypeScript, Tailwind, shadcn/ui |
| API | Python FastAPI |
| DB | PostgreSQL (+ Redis for worker) |
| Auth / billing | Clerk + Convex |

## Local development

**Prerequisites:** Node.js 18+, Python 3.12+, Docker Desktop

### 1. Databases

```powershell
docker compose up -d
```

### 2. Python API (port 8001)

```powershell
cd services/api
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python scripts/seed_dev.py
uvicorn app.main:app --reload --port 8001
```

### 3. Next.js (port 3001)

```powershell
copy .env.example .env.local
# Fill Clerk + Convex keys; set NEXT_PUBLIC_MIMIR_API_URL and NEXT_PUBLIC_DEV_SHOP_ID
npm install
npx convex dev
npm run dev -- -p 3001
```

**URLs**

- Landing: http://localhost:3001
- POS: http://localhost:3001/pos
- Admin: http://localhost:3001/admin/dashboard
- API docs: http://localhost:8001/docs

**Essential `.env.local` vars**

```
NEXT_PUBLIC_MIMIR_API_URL=http://localhost:8001
NEXT_PUBLIC_DEV_SHOP_ID=<id from seed_dev.py>
CORS_ORIGINS=http://localhost:3000,http://localhost:3001
# + Clerk and Convex keys from .env.example
```

Admin billing is bypassed in dev when `NEXT_PUBLIC_DEV_SHOP_ID` is set.

**API tests**

```powershell
cd services/api
python -m pytest tests/ -v
```

## Project layout

```
app/                  # Next.js routes (landing, pos, admin, onboarding)
components/           # Shared UI
convex/               # Users + subscription tracking
lib/                  # mimir-api.ts, admin-api.ts → FastAPI
services/api/         # FastAPI brain, models, routers, sync worker
docs/                 # Auth/setup notes
```

## Docs

| File | Purpose |
|------|---------|
| [PLAN.md](./PLAN.md) | Phase status and build rules |
| [DEPLOY.md](./DEPLOY.md) | Vercel + Railway + Neon deploy |
| [FEATURE_PARITY.md](./FEATURE_PARITY.md) | Partner feature matrix |
| [docs/CLERK_CONVEX_AUTH.md](./docs/CLERK_CONVEX_AUTH.md) | Clerk JWT for Convex |

## Deploy

See [DEPLOY.md](./DEPLOY.md). Target stack: Vercel (UI), Railway (API + worker), Neon (Postgres), Clerk + Convex (auth/billing).

## Phase status

Phases 0–6 (foundation through SaaS launch) are complete. Phase 7 (OCR intake, native app) is post-launch — see [PLAN.md](./PLAN.md).
