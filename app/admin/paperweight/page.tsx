"use client";

// Slice-12 read-only Paperweight Report.
//
// Backed only by the accepted authenticated GET /api/v1/admin/inventory/
// paperweight contract (paperweight_queue): an uncapped unit total plus at
// most the 100 oldest in-stock items added before the shop's cutoff, each
// with id, sku, name, stock, price, date_added only. The cutoff is the
// shop's paperweight setting (60 days by default); the response does not
// say which value is configured, so this screen never states it as fact.
// Missing values render as "—". No discount, reprice, relist, export, or
// mutation of any kind; no cost, margin, or suggested-price is inferred.

import { useEffect, useRef, useState } from "react";
import { mimirApi, type PaperweightItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import {
  formatPaperweightDate,
  formatPaperweightMoney,
  paperweightListNotice,
} from "@/lib/paperweight";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";

/** Mobile card. Mirrors the table row data, never writes. */
function PaperweightCard({ item }: { item: PaperweightItem }) {
  return (
    <div className="rounded-lg border border-border bg-gunmetal p-4">
      <p className="min-w-0 flex-1 text-sm font-medium text-foreground">{item.name}</p>
      <p className="mt-1 font-mono text-xs text-steel">{item.sku}</p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="text-xs text-steel">added {formatPaperweightDate(item.date_added)}</span>
        <span className="text-foreground">stock {item.stock}</span>
        <span className="text-foreground">{formatPaperweightMoney(item.price)}</span>
      </div>
    </div>
  );
}

export default function PaperweightPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [items, setItems] = useState<PaperweightItem[]>([]);
  const [units, setUnits] = useState<number | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    // A shop switch clears the previous shop's report immediately and
    // aborts any in-flight response from that shop.
    const controller = new AbortController();
    setItems([]);
    setUnits(null);
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
        const data = await mimirApi.paperweightReport({
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
        setItems(data.items ?? []);
        setUnits(typeof data.units === "number" ? data.units : null);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setItems([]);
        setUnits(null);
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
        title="Paperweight Report"
        subtitle={`In-stock items at ${selectedShop?.name} added before the shop's paperweight cutoff (60 days by default; each shop's own setting may differ). Oldest first. Read-only; discounting and relisting are not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>units unavailable</span>
            ) : loading || units === null ? (
              <span>counting…</span>
            ) : (
              <>
                <span className={units > 0 ? "text-ember" : "text-foreground"}>{units}</span>{" "}
                {units === 1 ? "stagnant unit" : "stagnant units"}
              </>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {loading
          ? "Loading paperweight report"
          : errorText
            ? errorText
            : `${items.length} paperweight items shown`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading paperweight report…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {!errorText && units !== null ? (
            <p className="mb-4 rounded-lg border border-border bg-gunmetal p-3 font-mono text-xs text-steel">
              {items.length === 0
                ? "No in-stock items are past this shop's paperweight cutoff right now. Stock is turning over."
                : paperweightListNotice(items.length, units)}
            </p>
          ) : null}

          {/* Desktop/tablet table */}
          {items.length > 0 ? (
            <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-gunmetal">
                    <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Item</th>
                    <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Added (UTC)</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Stock</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Price</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className="border-b border-border/60">
                      <td className="p-3 text-foreground">
                        {item.name}
                        <span className="block font-mono text-xs text-steel">{item.sku}</span>
                      </td>
                      <td className="p-3 font-mono text-steel">{formatPaperweightDate(item.date_added)}</td>
                      <td className="p-3 text-right font-mono text-foreground">{item.stock}</td>
                      <td className="p-3 text-right font-mono text-foreground">
                        {formatPaperweightMoney(item.price)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Paperweight items">
            {items.map((item) => (
              <PaperweightCard key={item.id} item={item} />
            ))}
          </section>
        </>
      )}
    </div>
  );
}
