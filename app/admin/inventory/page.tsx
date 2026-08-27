"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { itemSellPrice, mimirApi, type InventoryItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";

export default function AdminInventoryPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<"idle" | "empty" | "results" | "error">("idle");
  const [errorText, setErrorText] = useState("");
  const [writeHint, setWriteHint] = useState(false);
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  const queryRef = useRef(q);
  shopIdRef.current = shopId;
  queryRef.current = q;

  const load = useCallback(
    async (signal?: AbortSignal) => {
      if (!shopId) return;
      const requestedShopId = shopId;
      setLoading(true);
      setErrorText("");
      try {
        const data = await mimirApi.searchInventory(queryRef.current, {
          shopId: requestedShopId,
          limit: 100,
          signal,
        });
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current) || signal?.aborted) return;
        const rows = data.items ?? [];
        setItems(rows);
        setTotal(data.total);
        setStatus(rows.length === 0 ? "empty" : "results");
      } catch (err) {
        if (signal?.aborted) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setItems([]);
        setTotal(0);
        setStatus("error");
        setErrorText(classified.message);
      } finally {
        if (!signal?.aborted && shouldApplyShopResult(requestedShopId, shopIdRef.current)) {
          setLoading(false);
        }
      }
    },
    [reportApiError, shopId]
  );

  useEffect(() => {
    const controller = new AbortController();
    setItems([]);
    setTotal(0);
    setErrorText("");
    setStatus("idle");
    setWriteHint(false);
    if (shopId) void load(controller.signal);
    else setLoading(false);
    return () => controller.abort();
  }, [shopId, load]);

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Inventory
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-steel">
            Read-only search for {selectedShop?.name}. Edits, labels, and imports are not ready.
          </p>
        </div>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel">
          <span className="text-neon">{total}</span> in-stock rows
        </p>
      </div>

      <div className="mb-4 flex gap-2">
        <Input
          placeholder="Search name, SKU, or set…"
          className="min-h-11 border-border bg-surface font-mono text-sm focus-visible:border-neon"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void load()}
          aria-label="Search inventory"
        />
        <Button
          onClick={() => void load()}
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
          : status === "empty"
            ? "No in-stock cards matched"
            : `${items.length} results`}
      </div>

      {status === "error" ? (
        <p className="mb-4 rounded-md border border-border bg-gunmetal p-3 text-sm text-steel" role="alert">
          {errorText}
        </p>
      ) : null}

      {loading ? (
        <div className="h-40 animate-pulse rounded-lg bg-gunmetal motion-reduce:animate-none" role="status">
          Loading inventory…
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
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
              {items.map((item) => (
                <tr key={item.sku} className="border-b border-border/60">
                  <td className="p-3 font-mono text-xs text-steel">{item.sku}</td>
                  <td className="p-3 text-foreground">{item.name}</td>
                  <td className="p-3 text-right font-mono">{item.stock}</td>
                  <td className="p-3 text-right font-mono text-neon">${itemSellPrice(item).toFixed(2)}</td>
                </tr>
              ))}
              {status === "empty" ? (
                <tr>
                  <td colSpan={4} className="p-10 text-center font-mono text-sm text-steel">
                    No in-stock cards matched this search. This is an empty result, not a failed write.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-4">
        <Button type="button" variant="outline" className="min-h-11" onClick={() => setWriteHint(true)}>
          Edit stock / print labels
        </Button>
        {writeHint ? (
          <FeatureNotReady
            title="Inventory writes are not ready"
            detail="Stock edits, QR labels, resticker, and CSV quantity changes are deferred."
          />
        ) : null}
      </div>
    </div>
  );
}
