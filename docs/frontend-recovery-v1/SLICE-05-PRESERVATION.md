# Slice-05 POS Find full stock browse — preservation record

**Slice:** `frontend-recovery-v1 / slice-05-pos-find-full-stock-browse`  
**Base:** `main` `990da8a`  
**Contract:** accepted authenticated `GET /api/v1/inventory/search`
(D-029 read-ready; exact barcode/SKU priority, `total`, `offset`/`limit`,
shop-scoped, in-stock only). No backend change; the offset parameter
already existed server-side.

## What was recovered on `/pos/find`

- Honest total: "N in-stock match(es)." rendered from the contract
  `total`, never from the current page length.
- Offset pagination (50 per page): Previous/Next buttons with
  "X–Y of N" window, disabled at the boundaries, "End of results." on the
  last page.
- Reset discipline: submitting a new query or switching shops restarts at
  page 0 and aborts/discards in-flight responses; an epoch counter rejects
  any response superseded by a newer search (`shouldApplyShopResult` kept).
- Exact SKU/barcode fast path: when the contract returns `total=1` for a
  case-insensitive exact SKU match, the card is rendered with an
  "Exact SKU/barcode match" badge. Partial or ambiguous results remain the
  normal list. USB barcode wedges work as keyboard input ending in Enter.
- States: loading, empty ("empty result, not a failed write"), error with
  classified session-expired / forbidden / feature-not-ready messages.
- Read-only by construction: no checkout, sell, reserve, auto-select, or
  mutation path anywhere in the touched code.

## Partner behavioural reference (behaviour only, no code copied)

The partner desktop app's floor lookup is the behavioural reference:
fast SKU/name find with a barcode wedge on the show floor, immediate
single-card answer on an exact code. Recorded per
`docs/frontend-recovery-v1/SCREEN-INVENTORY.md` ("Partner behavior to
preserve"). No partner source was copied or ported; the implementation
uses only the accepted FastAPI contract.

## Preserved and untouched

- POS Find visual language (gunmetal cards, neon accents, mono metadata),
  membership shell (`app/pos/layout.tsx` VendorShopProvider +
  ShopAccessGate), keyboard/mobile tap targets (min-h-12 controls,
  labelled nav).
- Fixtures in tests are clearly labeled synthetic data; staging may only
  prove the honest empty state. No camera scanning, barcode images,
  writes, intake, Shopify, providers, backend, deployment, or seed data.
