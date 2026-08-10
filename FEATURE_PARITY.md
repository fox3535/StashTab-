# StashTab (Mimir SaaS) — Partner Feature Parity

> Last updated: 2026-07-13

## Status vs partner desktop brain

| Partner feature | Python brain | API | UI | Notes |
|---|---|---|---|---|
| Collectr import + recon | ✅ | ✅ | ✅ | Removal CSV export + missing-in-Collectr list |
| Persistent SKU | ✅ | ✅ | ✅ | Reuses inventory SKU on re-acquisition |
| Barcode / QR labels | ✅ | ✅ | ✅ | Inventory **QR** button; `/static/barcodes/` |
| Manual intake (single + sealed) | ✅ | ✅ | ✅ | |
| Multi-TCG | ✅ | ✅ | ✅ | POS game filter; CSV One Piece adapter |
| Local image repo | ✅ | ✅ | ✅ | `/static/scraped_thumbnails/{sku}.png` |
| Paperweight (60+ days) | ✅ | ✅ | ✅ | Dashboard KPI + `/admin/paperweight` |
| Live barcode POS | ✅ | ✅ | ✅ | Exact SKU match + scan-to-cart |
| Mobile-web checkout | ✅ | ✅ | ✅ | `/pos` cloud-hosted (replaces Cloudflare Tunnel) |
| Placeholder trades | ✅ | ✅ | ✅ | Uses shop trade % from settings |
| Weighted cost distribution | ✅ | ✅ | ✅ | Staging → Apply trade values |
| Real-time Shopify sync | ✅ | ✅ | ✅ | Worker respects `auto_sync_enabled` |
| Dynamic pricing engine | ✅ | ✅ | ✅ | Markup, rounding, shipping rules UI |
| Market price snapshots | ✅ | ✅ | ✅ | Stats → Capture Show Prices |
| Repricing / resticker alerts | ✅ | ✅ | ✅ | Threshold in Settings |
| Sync discrepancy reporting | ✅ | ✅ | ✅ | Collectr recon + Shopify verify |

## SaaS equivalents

- **Cloudflare Tunnel** → Vercel `/pos` + Railway API (always-on HTTPS). No LAN tunnel needed.
- **Desktop printer spool** → generate QR PNG in browser; print from phone/OS.
- **Local Flask checkout** → hosted StashTab POS.

## Still post-launch (Phase 7)

- OCR camera intake
- Native app shell
- Direct Collectr API write-back (partner is CSV-only too)
