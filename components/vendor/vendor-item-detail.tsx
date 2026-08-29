"use client";

// Slice-07 shared read-only vendor item detail.
//
// One focused experience usable from POS Find and admin inventory, backed
// only by the accepted authenticated GET /api/v1/inventory/{sku} contract
// (get_by_sku, InventoryItemOut): shop-scoped uppercase SKU lookup, 404
// when the item is not listed for the selected shop. Only contract-backed
// fields are rendered — the response has no barcode and no location field,
// so nothing about those is shown or inferred. Membership authority, Clerk
// bearer auth, and the selected-shop hint are handled by the existing
// mimir-api client and vendor shell; epoch/abort + shouldApplyDetailResult
// discard late responses across SKU changes and shop switches.
//
// Read-only by construction: no sell, reserve, edit, adjust, intake,
// Shopify, notification, payment, or Watch action exists here.

import { useEffect, useRef, useState, type ReactNode } from "react";
import { ArrowLeft } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { itemSellPrice, mimirApi, type InventoryItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { normalizeDetailSku, shouldApplyDetailResult } from "@/lib/item-detail";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { VendorErrorBanner, VendorLoadingBlock } from "@/components/vendor/vendor-patterns";
import { cn } from "@/lib/utils";

function DetailRow({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 border-b border-border/60 py-2">
      <dt className="font-mono text-[10px] uppercase tracking-[0.18em] text-steel">{label}</dt>
      <dd className="font-mono text-sm text-foreground">{value ?? ""}</dd>
    </div>
  );
}

export function VendorItemDetail({
  sku,
  onBack,
  renderThumbnail,
  backClassName = "min-h-11",
  backLabel = "Back to results",
}: {
  /** The actual SKU returned by the accepted search contract. */
  sku: string;
  onBack: () => void;
  /** Optional image renderer supplied by the page (e.g. CardThumbnail). */
  renderThumbnail?: (item: InventoryItem) => ReactNode;
  backClassName?: string;
  backLabel?: string;
}) {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);
  const backButtonRef = useRef<HTMLButtonElement>(null);

  const normalizedSku = normalizeDetailSku(sku);
  const [item, setItem] = useState<InventoryItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    backButtonRef.current?.focus();
  }, []);

  useEffect(() => {
    // A new SKU or shop switch clears the previous record and aborts any
    // in-flight lookup; late responses are discarded by the guards below.
    const controller = new AbortController();
    setItem(null);
    setErrorText("");
    if (!normalizedSku || !shopId) {
      setLoading(false);
      return () => controller.abort();
    }
    epochRef.current += 1;
    const myEpoch = epochRef.current;
    const requestedShopId = shopId;
    setLoading(true);
    (async () => {
      try {
        const data = await mimirApi.getInventoryBySku(normalizedSku, {
          shopId: requestedShopId,
          signal: controller.signal,
        });
        if (!shouldApplyDetailResult(myEpoch, epochRef.current, requestedShopId, shopIdRef.current)) return;
        setItem(data);
      } catch (err) {
        if (controller.signal.aborted) return;
        if (!shouldApplyDetailResult(myEpoch, epochRef.current, requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setErrorText(
          classified.kind === "not_found"
            ? `SKU ${normalizedSku} is not listed for ${selectedShop?.name ?? "this shop"}.`
            : classified.message
        );
      } finally {
        if (
          !controller.signal.aborted &&
          shouldApplyDetailResult(myEpoch, epochRef.current, requestedShopId, shopIdRef.current)
        ) {
          setLoading(false);
        }
      }
    })();
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [normalizedSku, shopId]);

  const sellPrice = item ? itemSellPrice(item) : 0;

  return (
    <section aria-label="Item detail" className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <Button
          ref={backButtonRef}
          type="button"
          variant="outline"
          className={cn("border-border font-mono text-sm", backClassName)}
          onClick={onBack}
          aria-label={backLabel}
        >
          <ArrowLeft className="size-4" />
          Back
        </Button>
        <p className="font-mono text-xs text-steel">
          Read-only record for {selectedShop?.name}. Selling, edits, labels, and adjustments are not ready.
        </p>
      </div>

      {errorText ? <VendorErrorBanner message={errorText} /> : null}

      {loading ? <VendorLoadingBlock label="Loading item…" className="h-32 p-3 font-mono text-sm text-steel" /> : null}

      {!loading && item ? (
        <div className="rounded-lg border border-border bg-gunmetal p-4 md:p-6">
          <div className="flex gap-4">
            {renderThumbnail ? renderThumbnail(item) : null}
            <div className="min-w-0 flex-1">
              <h2 className="font-display text-lg font-semibold text-foreground">{item.name}</h2>
              <p className="font-mono text-xs text-steel">{item.sku}</p>
              <div className="mt-2 flex flex-wrap items-center gap-3 font-mono text-sm">
                <span className="font-semibold text-neon">${sellPrice.toFixed(2)}</span>
                <Badge variant="outline" className="border-border font-mono text-steel">
                  {item.stock} in stock
                </Badge>
              </div>
            </div>
          </div>
          <dl className="mt-4">
            <DetailRow label="Set" value={item.set_name ?? "—"} />
            {item.sequence_number ? <DetailRow label="Number" value={item.sequence_number} /> : null}
            <DetailRow label="Game" value={item.game} />
            {item.card_type ? <DetailRow label="Type" value={item.card_type} /> : null}
            {item.variant ? <DetailRow label="Variant" value={item.variant} /> : null}
            {item.condition ? <DetailRow label="Condition" value={item.condition} /> : null}
            {item.sticker_price && item.sticker_price > 0 && item.sticker_price !== item.price ? (
              <DetailRow label="Sticker price" value={`$${item.sticker_price.toFixed(2)}`} />
            ) : null}
          </dl>
        </div>
      ) : null}
    </section>
  );
}
