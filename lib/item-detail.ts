// Slice-07 POS item detail — pure helpers.
//
// The accepted authenticated GET /api/v1/inventory/{sku} contract
// (services/api/app/routers/inventory.py get_by_sku, InventoryItemOut)
// looks up an item by shop-scoped uppercase SKU and returns 404 when it
// does not exist. The response has no barcode field, so detail identity is
// SKU-only — opened exclusively from an actually returned SKU, never
// inferred. This screen is read-only: it never sells, reserves, edits,
// adjusts, or mutates inventory.

/**
 * Normalize a SKU for the detail lookup. Mirrors the server's
 * `InventoryItem.sku == sku.upper()` comparison. Returns "" for anything
 * that is not a usable SKU so callers never fire an empty lookup.
 */
export function normalizeDetailSku(sku: string | null | undefined): string {
  return (sku ?? "").trim().toUpperCase();
}

/**
 * Guard for detail responses: a response may land only when its request is
 * still the latest one (epoch) and was made for the shop that is still
 * selected. Shop switches and newer lookups discard late responses.
 */
export function shouldApplyDetailResult(
  myEpoch: number,
  currentEpoch: number,
  requestShopId: string,
  currentShopId: string | null | undefined
): boolean {
  return (
    myEpoch === currentEpoch &&
    Boolean(currentShopId) &&
    requestShopId === currentShopId
  );
}
