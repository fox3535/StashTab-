"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { itemSellPrice, mimirApi, type InventoryItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import {
  FIND_PAGE_SIZE,
  classifyFindResponse,
  findPageWindow,
  offsetForPage,
  pageAfterReset,
} from "@/lib/pos-find";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";
import {
  BrowsePagination,
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";
import { VendorItemDetail } from "@/components/vendor/vendor-item-detail";

/** Mobile/tablet-fallback card. Mirrors the table row data, never writes. */
function InventoryCard({
  item,
  exact,
  onOpenDetail,
}: {
  item: InventoryItem;
  exact?: boolean;
  onOpenDetail: (sku: string) => void;
}) {
  return (
    <div
      className={
        exact
          ? "rounded-lg border border-neon/50 bg-neon/5 p-4"
          : "rounded-lg border border-border bg-gunmetal p-4"
      }
    >
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-sm font-medium text-foreground">{item.name}</p>
        {exact ? (
          <Badge className="border-neon/40 bg-neon/10 font-mono text-neon">
            Exact SKU match
          </Badge>
        ) : null}
      </div>
      <p className="mt-1 font-mono text-xs text-steel">
        {item.sku} · {item.set_name ?? "—"}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="font-semibold text-neon">${itemSellPrice(item).toFixed(2)}</span>
        <Badge variant="outline" className="border-border font-mono text-steel">
          {item.stock} qty
        </Badge>
        <Button
          type="button"
          variant="outline"
          className="min-h-11 border-border font-mono text-xs"
          onClick={() => onOpenDetail(item.sku)}
          aria-label={`View details for SKU ${item.sku}`}
        >
          Details
        </Button>
      </div>
    </div>
  );
}

export default function AdminInventoryPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [errorText, setErrorText] = useState("");
  const [writeHint, setWriteHint] = useState(false);
  const [detailSku, setDetailSku] = useState("");

  const runSearch = useCallback(
    async (q: string, targetPage: number, signal?: AbortSignal) => {
      if (!shopId) return;
      // A new request supersedes every earlier one; its response must never
      // land after a newer search or a shop switch.
      epochRef.current += 1;
      const myEpoch = epochRef.current;
      const requestedShopId = shopId;
      setLoading(true);
      setErrorText("");
      try {
        const data = await mimirApi.searchInventory(q, {
          shopId: requestedShopId,
          limit: FIND_PAGE_SIZE,
          offset: offsetForPage(targetPage, FIND_PAGE_SIZE),
          signal,
        });
        if (
          myEpoch !== epochRef.current ||
          !shouldApplyShopResult(requestedShopId, shopIdRef.current) ||
          signal?.aborted
        ) {
          return;
        }
        setItems(data.items ?? []);
        setTotal(typeof data.total === "number" ? data.total : data.items?.length ?? 0);
        setPage(targetPage);
        setSubmittedQuery(q);
        setLoaded(true);
      } catch (err) {
        if (signal?.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setItems([]);
        setTotal(0);
        setErrorText(classified.message);
      } finally {
        if (
          !signal?.aborted &&
          myEpoch === epochRef.current &&
          shouldApplyShopResult(requestedShopId, shopIdRef.current)
        ) {
          setLoading(false);
        }
      }
    },
    [reportApiError, shopId]
  );

  function submitSearch() {
    // A new query always restarts pagination at page 0.
    void runSearch(query, pageAfterReset());
  }

  useEffect(() => {
    // A shop switch resets to a fresh page-0 browse and aborts/discards any
    // in-flight response from the previous shop.
    const controller = new AbortController();
    setQuery("");
    setSubmittedQuery("");
    setItems([]);
    setTotal(0);
    setLoaded(false);
    setPage(pageAfterReset());
    setErrorText("");
    setWriteHint(false);
    // A shop switch closes any open detail so no stale shop's record
    // survives.
    setDetailSku("");
    if (shopId) void runSearch("", pageAfterReset(), controller.signal);
    else setLoading(false);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  const mode = classifyFindResponse(submittedQuery, total, items[0]?.sku);
  const windowInfo = findPageWindow(total, offsetForPage(page, FIND_PAGE_SIZE), FIND_PAGE_SIZE);
  const searched = submittedQuery.trim().length > 0;
  const emptyText = searched
    ? "No in-stock cards matched this search. This is an empty result, not a failed write."
    : "No in-stock cards are listed for this shop yet. This is an empty result, not a failed write.";

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <PageHeader
        className="mb-5"
        title="Inventory"
        subtitle={`Read-only browse and search for ${selectedShop?.name}. Edits, labels, and imports are not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>total unavailable</span>
            ) : !loaded ? (
              <span>counting…</span>
            ) : (
              <>
                <span className="text-neon">{total}</span>{" "}
                {searched ? (total === 1 ? "in-stock match" : "in-stock matches") : "in-stock rows"}
              </>
            )}
          </p>
        }
      />

      {detailSku ? (
        <VendorItemDetail sku={detailSku} onBack={() => setDetailSku("")} />
      ) : (
        <>
      <div className="mb-4 flex gap-2">
        <Input
          placeholder="Search name, SKU, or set…"
          className="min-h-11 border-border bg-surface font-mono text-sm focus-visible:border-neon"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
          aria-label="Search inventory"
        />
        <Button
          onClick={submitSearch}
          className="min-h-11 bg-neon font-display font-bold text-white hover:bg-neon/90"
          disabled={loading}
        >
          <Search className="size-4" />
          Search
        </Button>
      </div>

      <div aria-live="polite" className="sr-only">
        {loading
          ? "Loading inventory"
          : errorText
            ? errorText
            : `${items.length} rows on this page, ${total} total`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading inventory…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {/* Desktop/tablet table */}
          <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border bg-gunmetal">
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">SKU</th>
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Name</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Stock</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Price</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const exact = mode === "exact" && item.sku === items[0]?.sku;
                  return (
                    <tr
                      key={item.sku}
                      className={
                        exact
                          ? "border-b border-border/60 bg-neon/5"
                          : "border-b border-border/60"
                      }
                    >
                      <td className="p-3 font-mono text-xs text-steel">
                        <span className="flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            className="font-mono underline-offset-2 hover:text-foreground hover:underline focus-visible:outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50 rounded-sm"
                            onClick={() => setDetailSku(item.sku)}
                            aria-label={`View details for SKU ${item.sku}`}
                          >
                            {item.sku}
                          </button>
                          {exact ? (
                            <Badge className="border-neon/40 bg-neon/10 font-mono text-neon">
                              Exact SKU match
                            </Badge>
                          ) : null}
                        </span>
                      </td>
                      <td className="p-3 text-foreground">{item.name}</td>
                      <td className="p-3 text-right font-mono">{item.stock}</td>
                      <td className="p-3 text-right font-mono text-neon">
                        ${itemSellPrice(item).toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
                {items.length === 0 && !errorText ? (
                  <tr>
                    <td colSpan={4} className="p-10 text-center font-mono text-sm text-steel">
                      {emptyText}
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Inventory rows">
            {items.map((item) => (
              <InventoryCard
                key={item.sku}
                item={item}
                exact={mode === "exact" && item.sku === items[0]?.sku}
                onOpenDetail={setDetailSku}
              />
            ))}
            {items.length === 0 && !errorText ? (
              <p className="py-8 text-center font-mono text-sm text-steel">{emptyText}</p>
            ) : null}
          </section>
        </>
      )}

      {!loading && !errorText && total > 0 ? (
        <BrowsePagination
          windowInfo={windowInfo}
          total={total}
          onPrev={() => void runSearch(submittedQuery, page - 1)}
          onNext={() => void runSearch(submittedQuery, page + 1)}
          className="mt-4"
        />
      ) : null}
        </>
      )}

      {!detailSku ? (
        <div className="mt-4">
          <Button
            type="button"
            variant="outline"
            className="min-h-11"
            onClick={() => setWriteHint(true)}
          >
            Edit stock / print labels
          </Button>
          {writeHint ? (
            <FeatureNotReady
              title="Inventory writes are not ready"
              detail="Stock edits, adjustments, QR labels, resticker, CSV imports, intake, Shopify sync, notifications, payments, and Watch are deferred. This screen is read-only."
            />
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
