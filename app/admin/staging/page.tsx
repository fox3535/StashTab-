"use client";

// Slice-15 read-only Staging Queue.
//
// Backed only by the accepted authenticated GET /api/v1/admin/staging
// contract (list_staging): at most the 100 newest staged items, newest
// first, each with id, sku, name, set_name, sequence_number, market_price,
// suggested_price, image_url, quantity, condition, variant, card_type,
// needs_review. cost_basis is never returned or shown. Committing staging
// is the inventory-truth receive path (held F2 work): this screen has no
// commit, commit-all, edit, refetch, remove, or apply-trades behaviour of
// any kind. Decisions: docs/frontend-recovery-v1/PLAN-SLICE-15-STAGING-QUEUE.md.

import { useEffect, useRef, useState } from "react";
import { mimirApi, type StagingQueueItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import {
  formatStagingMoney,
  stagingConditionLine,
  stagingListNotice,
  stagingSetLine,
} from "@/lib/staging-queue";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";
import { CardThumbnail } from "@/app/pos/components/card-thumbnail";

function thumbnailFor(item: StagingQueueItem) {
  return { name: item.name ?? item.sku, image_url: item.image_url };
}

function ReviewBadge({ item }: { item: StagingQueueItem }) {
  if (!item.needs_review) return null;
  return (
    <span className="ml-2 inline-block rounded border border-border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-steel">
      needs review
    </span>
  );
}

/** Mobile card. Mirrors the table row data, never writes. */
function StagingCard({ item }: { item: StagingQueueItem }) {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-gunmetal p-4">
      <CardThumbnail item={thumbnailFor(item)} size="sm" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-foreground">
          {item.name ?? "—"}
          <ReviewBadge item={item} />
        </p>
        <p className="mt-1 font-mono text-xs text-steel">{item.sku}</p>
        <p className="mt-1 text-xs text-steel">{stagingSetLine(item.set_name, item.sequence_number)}</p>
        <p className="mt-1 text-xs text-foreground">{stagingConditionLine(item.condition, item.variant)}</p>
        <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
          <span className="text-foreground">qty {item.quantity ?? "—"}</span>
          <span className="text-xs text-steel">market {formatStagingMoney(item.market_price)}</span>
          <span className="font-semibold text-neon">suggested {formatStagingMoney(item.suggested_price)}</span>
        </div>
      </div>
    </div>
  );
}

export default function StagingPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [items, setItems] = useState<StagingQueueItem[]>([]);
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
        const data = await mimirApi.stagingQueue({
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
        title="Staging Queue"
        subtitle={`Identified items at ${selectedShop?.name} waiting to enter inventory, newest first. Read-only; committing to inventory, editing, removing, and applying trades are not ready.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {errorText ? (
              <span>count unavailable</span>
            ) : loading ? (
              <span>counting…</span>
            ) : (
              <>
                <span className="text-neon">{items.length}</span>{" "}
                {items.length === 1 ? "staged item" : "staged items"}
              </>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {loading
          ? "Loading staging queue"
          : errorText
            ? errorText
            : `${items.length} staged items shown`}
      </div>

      {errorText ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {loading ? (
        <VendorLoadingBlock
          label="Loading staging queue…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : (
        <>
          {!errorText ? (
            <p className="mb-4 rounded-lg border border-border bg-gunmetal p-3 font-mono text-xs text-steel">
              {items.length === 0
                ? "Nothing is waiting in staging for this shop. This is an empty result, not a failed write."
                : `${stagingListNotice(items.length)} Market price comes from card data and is not your price.`}
            </p>
          ) : null}

          {/* Desktop/tablet table */}
          {items.length > 0 ? (
            <div className="hidden overflow-x-auto rounded-lg border border-border md:block">
              <table className="w-full min-w-[760px] text-sm">
                <thead>
                  <tr className="border-b border-border bg-gunmetal">
                    <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">
                      <span className="sr-only">Image</span>
                    </th>
                    <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Item</th>
                    <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Condition</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Qty</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Market price</th>
                    <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Suggested sell price</th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((item) => (
                    <tr key={item.id} className="border-b border-border/60 align-top">
                      <td className="p-3">
                        <CardThumbnail item={thumbnailFor(item)} size="sm" />
                      </td>
                      <td className="p-3 text-foreground">
                        {item.name ?? "—"}
                        <ReviewBadge item={item} />
                        <span className="block font-mono text-xs text-steel">{item.sku}</span>
                        <span className="block text-xs text-steel">{stagingSetLine(item.set_name, item.sequence_number)}</span>
                      </td>
                      <td className="p-3 text-foreground">{stagingConditionLine(item.condition, item.variant)}</td>
                      <td className="p-3 text-right font-mono text-foreground">{item.quantity ?? "—"}</td>
                      <td className="p-3 text-right font-mono text-steel">{formatStagingMoney(item.market_price)}</td>
                      <td className="p-3 text-right font-mono text-neon">{formatStagingMoney(item.suggested_price)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : null}

          {/* Mobile cards */}
          <section className="space-y-2 md:hidden" aria-label="Staged items">
            {items.map((item) => (
              <StagingCard key={item.id} item={item} />
            ))}
          </section>
        </>
      )}
    </div>
  );
}
