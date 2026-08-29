"use client";

// Slice-10 read-only Price Update review.
//
// Backed only by the accepted authenticated GET /api/v1/admin/
// inventory/updated contract (list_updated_cards): inventory records the
// API flagged needs_update == true — i.e. records carrying a
// pending/previous price update as defined by the API. Returns id, sku,
// name, old_price, price, shop_listing_price only, with NO cap and NO
// pagination. Missing optional values render as "—". No margin, market
// price, provider price, profit, recommended action, or completion
// status is inferred. No approve, dismiss, edit, reprice, export, or
// mutation of any kind; legacy pricing and resticker actions are not
// revived.

import { useEffect, useRef, useState } from "react";
import { mimirApi, type PendingPriceUpdate } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import {
  formatPriceUpdateMoney,
  priceUpdateSetNotice,
} from "@/lib/price-updates";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";

/** Mobile/tablet-fallback card. Mirrors the table row data, never writes. */
function PriceUpdateCard({ record }: { record: PendingPriceUpdate }) {
  return (
    <div className="rounded-lg border border-border bg-gunmetal p-4">
      <p className="min-w-0 flex-1 text-sm font-medium text-foreground">{record.name}</p>
      <p className="mt-1 font-mono text-xs text-steel">{record.sku}</p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="text-xs text-steel">
          old {formatPriceUpdateMoney(record.old_price)}
        </span>
        <span className="font-semibold text-neon">
          current {formatPriceUpdateMoney(record.price)}
        </span>
        <span className="text-xs text-steel">
          listing {formatPriceUpdateMoney(record.shop_listing_price)}
        </span>
      </div>
    </div>
  );
}

export default function PriceUpdatesPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [records, setRecords] = useState<PendingPriceUpdate[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    // A shop switch clears the previous shop's records immediately and
    // aborts any in-flight response from that shop.
    const controller = new AbortController();
    setRecords([]);
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
        const data = await mimirApi.priceUpdates({
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
        setRecords(data.items ?? []);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setRecords([]);
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
        title="Price Updates"
        subtitle={`Inventory records carrying a pending/previous price update for ${selectedShop?.name}, as defined by the API. Read-only; approving or repricing is not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>count unavailable</span>
            ) : loading ? (
              <span>counting…</span>
            ) : (
              <>
                <span className="text-neon">{records.length}</span>{" "}
                {records.length === 1 ? "price update" : "price updates"}
              </>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {loading
          ? "Loading price updates"
          : errorText
            ? errorText
            : `${records.length} price updates shown`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading price updates…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {!errorText ? (
            <p className="mb-4 rounded-lg border border-border bg-gunmetal p-3 font-mono text-xs text-steel">
              {records.length === 0
                ? "No inventory records carry a pending/previous price update for this shop right now. This is an empty result, not a failed write."
                : priceUpdateSetNotice(records.length)}
            </p>
          ) : null}

          {/* Desktop/tablet table */}
          <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
            <table className="w-full min-w-[640px] text-sm">
              <thead>
                <tr className="border-b border-border bg-gunmetal">
                  <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Item</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Old price</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Current price</th>
                  <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Shop listing price</th>
                </tr>
              </thead>
              <tbody>
                {records.map((record) => (
                  <tr key={record.id} className="border-b border-border/60">
                    <td className="p-3 text-foreground">
                      {record.name}
                      <span className="block font-mono text-xs text-steel">{record.sku}</span>
                    </td>
                    <td className="p-3 text-right font-mono text-steel">
                      {formatPriceUpdateMoney(record.old_price)}
                    </td>
                    <td className="p-3 text-right font-mono text-neon">
                      {formatPriceUpdateMoney(record.price)}
                    </td>
                    <td className="p-3 text-right font-mono text-foreground">
                      {formatPriceUpdateMoney(record.shop_listing_price)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Price update rows">
            {records.map((record) => (
              <PriceUpdateCard key={record.id} record={record} />
            ))}
          </section>
        </>
      )}
    </div>
  );
}
