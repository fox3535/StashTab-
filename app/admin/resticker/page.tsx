"use client";

// Slice-13 read-only Resticker Queue.
//
// Backed only by the accepted authenticated GET /api/v1/admin/inventory/
// resticker contract (list_resticker_queue): in-stock items whose recorded
// sticker price differs from the current price rounded up by at least the
// shop's resticker threshold ($2.00 by default). Returns id, sku, name,
// price, sticker_price, suggested_sticker only, sorted by name, with NO cap
// and NO pagination. suggested_sticker is the API's value; this screen never
// computes prices or differences. No mark-restickered, mark-all, label
// printing, or mutation of any kind.

import { useEffect, useRef, useState } from "react";
import { mimirApi, type RestickerItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import { formatRestickerMoney, restickerSetNotice } from "@/lib/resticker";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";

/** Mobile card. Mirrors the table row data, never writes. */
function RestickerCard({ item }: { item: RestickerItem }) {
  return (
    <div className="rounded-lg border border-border bg-gunmetal p-4">
      <p className="min-w-0 flex-1 text-sm font-medium text-foreground">{item.name}</p>
      <p className="mt-1 font-mono text-xs text-steel">{item.sku}</p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="text-xs text-steel">sticker {formatRestickerMoney(item.sticker_price)}</span>
        <span className="text-xs text-steel">price {formatRestickerMoney(item.price)}</span>
        <span className="font-semibold text-neon">
          suggested {formatRestickerMoney(item.suggested_sticker)}
        </span>
      </div>
    </div>
  );
}

export default function RestickerPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [items, setItems] = useState<RestickerItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    // A shop switch clears the previous shop's queue immediately and
    // aborts any in-flight response from that shop.
    const controller = new AbortController();
    setItems([]);
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
        const data = await mimirApi.restickerQueue({
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
      } catch (err) {
        if (controller.signal.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setItems([]);
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
        title="Resticker Queue"
        subtitle={`In-stock items at ${selectedShop?.name} whose printed sticker differs from the current price (rounded up) by at least the shop's resticker threshold ($2.00 by default; each shop's own setting may differ). Read-only; marking items restickered and printing labels are not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>count unavailable</span>
            ) : loading ? (
              <span>counting…</span>
            ) : (
              <>
                <span className="text-neon">{items.length}</span>{" "}
                {items.length === 1 ? "sticker to update" : "stickers to update"}
              </>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {loading
          ? "Loading resticker queue"
          : errorText
            ? errorText
            : `${items.length} resticker items shown`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading resticker queue…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {!errorText ? (
            <p className="mb-4 rounded-lg border border-border bg-gunmetal p-3 font-mono text-xs text-steel">
              {items.length === 0
                ? "No in-stock items have a sticker past this shop's resticker threshold right now. This is an empty result, not a failed write."
                : restickerSetNotice(items.length)}
            </p>
          ) : null}

          {/* Desktop/tablet table */}
          {items.length > 0 ? (
            <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
              <table className="w-full min-w-[640px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-gunmetal">
                    <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Item</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Current sticker</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Current price</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Suggested sticker</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className="border-b border-border/60">
                      <td className="p-3 text-foreground">
                        {item.name}
                        <span className="block font-mono text-xs text-steel">{item.sku}</span>
                      </td>
                      <td className="p-3 text-right font-mono text-steel">
                        {formatRestickerMoney(item.sticker_price)}
                      </td>
                      <td className="p-3 text-right font-mono text-foreground">
                        {formatRestickerMoney(item.price)}
                      </td>
                      <td className="p-3 text-right font-mono text-neon">
                        {formatRestickerMoney(item.suggested_sticker)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Resticker items">
            {items.map((item) => (
              <RestickerCard key={item.id} item={item} />
            ))}
          </section>
        </>
      )}
    </div>
  );
}
