// Pure POS Find browse state helpers (slice-05).
//
// Behavioural reference: the partner desktop app's floor lookup (fast
// SKU/name find with a barcode wedge). Recorded as behaviour only; no
// partner code is copied. Everything here is read-only state math for the
// accepted GET /api/v1/inventory/search contract — never sell, reserve,
// auto-select, or mutate inventory.

export const FIND_PAGE_SIZE = 50;

export interface FindPageWindow {
  /** 1-based index of the first visible result, 0 when there are none. */
  from: number;
  /** 1-based index of the last visible result. */
  to: number;
  hasPrev: boolean;
  hasNext: boolean;
  /** True when the current page reaches the end of the honest total. */
  endOfResults: boolean;
}

export function findPageWindow(total: number, offset: number, pageSize: number): FindPageWindow {
  const safeTotal = Math.max(0, total);
  const safeOffset = Math.max(0, offset);
  const from = safeTotal === 0 ? 0 : safeOffset + 1;
  const to = Math.min(safeOffset + pageSize, safeTotal);
  return {
    from,
    to,
    hasPrev: safeOffset > 0,
    hasNext: safeOffset + pageSize < safeTotal,
    endOfResults: safeOffset + pageSize >= safeTotal,
  };
}

export function offsetForPage(page: number, pageSize: number): number {
  return Math.max(0, page) * pageSize;
}

export type FindMode = "exact" | "list" | "empty";

/**
 * The accepted search contract returns a single item with total=1 when the
 * query exactly matches an in-stock SKU/barcode. Only that shape is the
 * fast-path exact match; anything else stays a normal result list.
 */
export function classifyFindResponse(
  query: string,
  total: number,
  firstSku: string | undefined
): FindMode {
  const q = query.trim().toUpperCase();
  if (total <= 0) return "empty";
  if (total === 1 && firstSku && q && firstSku.toUpperCase() === q) return "exact";
  return "list";
}

/** A new query or a shop switch always restarts pagination at page 0. */
export function pageAfterReset(): number {
  return 0;
}
