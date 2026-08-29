"use client";

// Slice-09 read-only Recent Trade History.
//
// Backed only by the accepted authenticated GET /api/v1/reports/
// trade-history contract (trade_history): genuinely trade-typed records
// (transaction_type == "trade") scoped to the verified membership's
// shop, newest-first, FIXED cap of 200 records, no pagination and no
// total. Only returned fields are displayed (ID, item name, SKU, sold
// price, trade-in value, timestamp); missing optional values render as
// "—". No totals, profit, margin, customer, payment, tax, or inventory
// data is invented. No trade creation, sale, refund, export, inventory
// mutation, Shopify, notification, payment, or Watch behavior. The
// legacy CSV export stub that lived here is deliberately not revived.

import { useEffect, useRef, useState } from "react";
import { mimirApi, type TradeRecord } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import {
  cappedTradeNotice,
  formatTradeMoney,
  formatTradeTimestamp,
} from "@/lib/trade-history";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";

/** Mobile/tablet-fallback card. Mirrors the table row data, never writes. */
function TradeCard({ trade }: { trade: TradeRecord }) {
  return (
    <div className="rounded-lg border border-border bg-gunmetal p-4">
      <p className="min-w-0 flex-1 text-sm font-medium text-foreground">
        {trade.item_name ?? "—"}
      </p>
      <p className="mt-1 font-mono text-xs text-steel">
        {trade.sku ?? "—"} · ID {trade.id}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="font-semibold text-neon">
          {formatTradeMoney(trade.sold_price)}
        </span>
        <span className="text-xs text-steel">
          trade-in {formatTradeMoney(trade.trade_in_value)}
        </span>
      </div>
      <p className="mt-1 font-mono text-xs text-steel">
        {formatTradeTimestamp(trade.timestamp)}
      </p>
    </div>
  );
}

export default function RecentTradeHistoryPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [trades, setTrades] = useState<TradeRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    // A shop switch clears the previous shop's trades immediately and
    // aborts any in-flight response from that shop.
    const controller = new AbortController();
    setTrades([]);
    setErrorText("");

    if (!shopId) {
      setLoading(false);
      return () => controller.abort();
    }

    // A new request supersedes every earlier one; its response must never
    // land after a newer request or a shop switch.
    epochRef.current += 1;
    const myEpoch = epochRef.current;
    const requestedShopId = shopId;
    setLoading(true);

    (async () => {
      try {
        const data = await mimirApi.recentTrades({
          shopId: requestedShopId,
          signal: controller.signal,
        });
        if (
          myEpoch !== epochRef.current ||
          !shouldApplyShopResult(requestedShopId, shopIdRef.current) ||
          controller.signal.aborted
        ) {
          return;
        }
        setTrades(data.trades ?? []);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setTrades([]);
        setErrorText(classified.message);
      } finally {
        if (
          !controller.signal.aborted &&
          myEpoch === epochRef.current &&
          shouldApplyShopResult(requestedShopId, shopIdRef.current)
        ) {
          setLoading(false);
        }
      }
    })();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <PageHeader
        className="mb-5"
        title="Recent Trade History"
        subtitle={`Genuinely trade-typed records for ${selectedShop?.name}. Read-only; the contract returns up to the newest 200 records and does not paginate. Exports and metrics are not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>count unavailable</span>
            ) : loading ? (
              <span>counting…</span>
            ) : (
              <>
                <span className="text-neon">{trades.length}</span>{" "}
                {trades.length === 1 ? "recent trade" : "recent trades"}
              </>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {loading
          ? "Loading recent trade history"
          : errorText
            ? errorText
            : `${trades.length} trades shown`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading recent trade history…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {!errorText ? (
            <p className="mb-4 rounded-lg border border-border bg-gunmetal p-3 font-mono text-xs text-steel">
              {trades.length === 0
                ? "No trade transactions are recorded for this shop yet. This is an empty result, not a failed write."
                : cappedTradeNotice(trades.length)}
            </p>
          ) : null}

          {/* Desktop/tablet table */}
          <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border bg-gunmetal">
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">When</th>
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Item</th>
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">ID</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Sold price</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Trade-in value</th>
                </tr>
              </thead>
              <tbody>
                {trades.map((trade) => (
                  <tr key={trade.id} className="border-b border-border/60">
                    <td className="whitespace-nowrap p-3 font-mono text-xs text-steel">
                      {formatTradeTimestamp(trade.timestamp)}
                    </td>
                    <td className="p-3 text-foreground">
                      {trade.item_name ?? "—"}
                      {trade.sku ? (
                        <span className="block font-mono text-xs text-steel">{trade.sku}</span>
                      ) : null}
                    </td>
                    <td className="p-3 font-mono text-xs text-steel">{trade.id}</td>
                    <td className="p-3 text-right font-mono text-neon">
                      {formatTradeMoney(trade.sold_price)}
                    </td>
                    <td className="p-3 text-right font-mono text-foreground">
                      {formatTradeMoney(trade.trade_in_value)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Recent trade rows">
            {trades.map((trade) => (
              <TradeCard key={trade.id} trade={trade} />
            ))}
          </section>
        </>
      )}
    </div>
  );
}
