# StashTab — Deployment Guide

## Architecture

| Service | Platform | Path |
|---------|----------|------|
| Next.js UI | Vercel | repo root |
| FastAPI | Railway | `services/api/` |
| Sync worker | Railway (2nd service) | `services/api/worker.py` |
| PostgreSQL | Neon | — |
| Auth/Billing | Clerk + Convex | — |

## 1. Neon (Postgres)

1. Create a project at [neon.tech](https://neon.tech)
2. Copy the connection string → `DATABASE_URL`
3. Run migrations / seed once from local:
   ```powershell
   cd services/api
   $env:DATABASE_URL="postgresql://..."
   python scripts/seed_dev.py
   ```

## 2. Railway (FastAPI + Worker)

### API service

- **Root directory:** `services/api`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Dockerfile:** use `services/api/Dockerfile`

**Environment variables:**

```
DATABASE_URL=postgresql://...
CORS_ORIGINS=https://your-app.vercel.app
CLERK_SECRET_KEY=sk_live_...
CLERK_JWT_ISSUER=https://your-clerk-domain.clerk.accounts.dev
DEV_SHOP_ID=          # leave empty in prod
```

### Worker service

- Same repo root `services/api`
- **Start command:** `python worker.py`
- Same `DATABASE_URL` and Shopify-related env as API
- **Scale:** 1 instance is enough for early launch

## 3. Vercel (Next.js)

- **Framework:** Next.js
- **Build:** `npm run build`

**Environment variables:**

```
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_live_...
CLERK_SECRET_KEY=sk_live_...
NEXT_PUBLIC_CONVEX_URL=https://....convex.cloud
NEXT_PUBLIC_MIMIR_API_URL=https://your-api.railway.app
CONVEX_DEPLOY_KEY=...
```

Do **not** set `NEXT_PUBLIC_DEV_SHOP_ID` in production.

## 4. Convex

```powershell
npx convex deploy
```

Configure Clerk webhook → Convex HTTP endpoint (users + subscription events).

## 5. Clerk

1. Create production application
2. Enable Billing / Pricing table (Free + Pro plans)
3. Add allowed redirect URLs for Vercel domain
4. Set JWT issuer URL → `CLERK_JWT_ISSUER` on Railway API

## 6. Custom domain

- **Vercel:** add domain in project settings → DNS CNAME
- **Railway API:** add custom domain → set `NEXT_PUBLIC_MIMIR_API_URL` on Vercel
- Update `CORS_ORIGINS` on API to include production URL

## 7. Smoke test after deploy

1. Sign up → `/onboarding` → create shop
2. Admin → Settings → Shopify credentials
3. `/pos` → search → checkout
4. Admin → Shopify Sync → Full sync

## Local dev (reference)

```powershell
docker compose up -d
cd services/api; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8001
npm run dev -- -p 3001
```
