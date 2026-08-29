"use client";

// Slice-08 read-only sales history browse.
//
// Backed only by the accepted authenticated GET /api/v1/sales/history
// contract (sales_history, SalesHistoryResponse): shop-scoped records,
// newest first, honest record-count total, limit/offset pagination. Only
// SaleOut fields are displayed and missing optional values render as "—".
// No sale creation, checkout, refund, cancellation, export, revenue
// metrics, trends, charts, or inferred customer/payment details.

import { useCallback, useEffect, useRef, useState } from "react";
import { Badge } from "@/components/ui/badge";
import { mimirApi, type SaleRecord } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import { findPageWindow, offsetForPage, pageAfterReset } from "@/lib/pos-find";
import { formatSaleMoney, formatSaleTimestamp, SALES_PAGE_SIZE } from "@/lib/sales-history";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  BrowsePagination,
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";

/** Mobile/tablet-fallback card. Mirrors the table row data, never writes. */
function SaleCard({ sale }: { sale: SaleRecord }) {
  return (
    <div className="rounded-lg border border-border bg-gunmetal p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="min-w-0 flex-1 text-sm font-medium text-foreground">
          {sale.item_name ?? "—"}
        </p>
        {sale.transaction_type ? (
          <Badge variant="outline" className="border-border font-mono text-steel">
            {sale.transaction_type}
          </Badge>
        ) : null}
      </div>
      <p className="mt-1 font-mono text-xs text-steel">
        {sale.sku ?? "—"} · {sale.game || "—"}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="font-semibold text-neon">{formatSaleMoney(sale.sold_price)}</span>
        <span className="text-xs text-steel">{formatSaleTimestamp(sale.timestamp)}</span>
      </div>
    </div>
  );
}

export default function SalesHistoryPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [sales, setSales] = useState<SaleRecord[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  const loadPage = useCallback(
    async (targetPage: number, signal?: AbortSignal) => {
      if (!shopId) return;
      // A new request supersedes every earlier one; its response must never
      // land after a newer request or a shop switch.
      epochRef.current += 1;
      const myEpoch = epochRef.current;
      const requestedShopId = shopId;
      setLoading(true);
      setErrorText("");
      try {
        const data = await mimirApi.salesHistory({
          shopId: requestedShopId,
          limit: SALES_PAGE_SIZE,
          offset: offsetForPage(targetPage, SALES_PAGE_SIZE),
          signal,
        });
        if (
          myEpoch !== epochRef.current ||
          !shouldApplyShopResult(requestedShopId, shopIdRef.current) ||
          signal?.aborted
        ) {
          return;
        }
        setSales(data.sales ?? []);
        setTotal(typeof data.total === "number" ? data.total : data.sales?.length ?? 0);
        setPage(targetPage);
      } catch (err) {
        if (signal?.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setSales([]);
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

  useEffect(() => {
    // A shop switch clears the previous shop's sales immediately and aborts
    // any in-flight response from that shop.
    const controller = new AbortController();
    setSales([]);
    setTotal(0);
    setPage(pageAfterReset());
    setErrorText("");
    if (shopId) void loadPage(pageAfterReset(), controller.signal);
    else setLoading(false);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  const windowInfo = findPageWindow(total, offsetForPage(page, SALES_PAGE_SIZE), SALES_PAGE_SIZE);

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <PageHeader
        className="mb-5"
        title="Sales History"
        subtitle={`Recorded sales for ${selectedShop?.name}. Read-only; refunds, exports, and metrics are not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>count unavailable</span>
            ) : loading ? (
              <span>counting…</span>
            ) : (
              <>
                <span className="text-neon">{total}</span>{" "}
                {total === 1 ? "recorded sale" : "recorded sales"}
              </>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {loading ? "Loading sales history" : errorText ? errorText : `${sales.length} rows on this page, ${total} total`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading sales history…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {/* Desktop/tablet table */}
          <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border bg-gunmetal">
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">When</th>
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Item</th>
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Game</th>
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Type</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Sold price</th>
                </tr>
              </thead>
              <tbody>
                {sales.map((sale) => (
                  <tr key={sale.id} className="border-b border-border/60">
                    <td className="whitespace-nowrap p-3 font-mono text-xs text-steel">
                      {formatSaleTimestamp(sale.timestamp)}
                    </td>
                    <td className="p-3 text-foreground">
                      {sale.item_name ?? "—"}
                      {sale.sku ? (
                        <span className="block font-mono text-xs text-steel">{sale.sku}</span>
                      ) : null}
                    </td>
                    <td className="p-3 text-foreground">{sale.game || "—"}</td>
                    <td className="p-3 font-mono text-xs text-steel">{sale.transaction_type ?? "—"}</td>
                    <td className="p-3 text-right font-mono text-neon">
                      {formatSaleMoney(sale.sold_price)}
                    </td>
                  </tr>
                ))}
                {sales.length === 0 && !errorText ? (
                  <tr>
                    <td colSpan={5} className="p-10 text-center font-mono text-sm text-steel">
                      No sales are recorded for this shop yet. This is an empty result, not a failed write.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Sales rows">
            {sales.map((sale) => (
              <SaleCard key={sale.id} sale={sale} />
            ))}
            {sales.length === 0 && !errorText ? (
              <p className="py-8 text-center font-mono text-sm text-steel">
                No sales are recorded for this shop yet. This is an empty result, not a failed write.
              </p>
            ) : null}
          </section>
        </>
      )}

      {!loading && !errorText && total > 0 ? (
        <BrowsePagination
          windowInfo={windowInfo}
          total={total}
          onPrev={() => void loadPage(page - 1)}
          onNext={() => void loadPage(page + 1)}
          className="mt-4"
        />
      ) : null}
    </div>
  );
}
