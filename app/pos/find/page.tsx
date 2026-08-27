"use client";

import { Suspense, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { itemSellPrice, mimirApi, type InventoryItem } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { CardThumbnail } from "../components/card-thumbnail";

function FindInner() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const [query, setQuery] = useState(initialQ);
  const [results, setResults] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  async function runSearch(q?: string, signal?: AbortSignal) {
    if (!shopId) return;
    const requestedShopId = shopId;
    setLoading(true);
    setErrorText("");
    try {
      const data = await mimirApi.searchInventory(q ?? query, {
        shopId: requestedShopId,
        limit: 50,
        signal,
      });
      if (!shouldApplyShopResult(requestedShopId, shopIdRef.current) || signal?.aborted) return;
      setResults(data.items ?? []);
    } catch (err) {
      if (signal?.aborted) return;
      if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
      const classified = classifyVendorError(err);
      reportApiError(err);
      setResults([]);
      setErrorText(classified.message);
    } finally {
      if (!signal?.aborted && shouldApplyShopResult(requestedShopId, shopIdRef.current)) {
        setLoading(false);
      }
    }
  }

  useEffect(() => {
    const controller = new AbortController();
    setResults([]);
    setErrorText("");
    if (shopId && (initialQ || query)) void runSearch(initialQ || query, controller.signal);
    else setLoading(false);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQ, shopId]);

  return (
    <div className="flex w-full max-w-full flex-col gap-4 overflow-x-hidden p-4 pt-[max(1rem,env(safe-area-inset-top))] md:p-6 lg:p-8">
      <header>
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">Find</h1>
        <p className="text-sm text-steel">
          Read-only booth lookup for {selectedShop?.name}. Selling is not ready.
        </p>
      </header>

      <div className="flex gap-2">
        <Input
          className="min-h-12 border-border bg-surface font-mono text-sm focus-visible:border-neon"
          placeholder="Scan barcode or search SKU..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && void runSearch()}
          aria-label="Search inventory"
        />
        <Button
          className="min-h-12 bg-neon font-display font-bold text-white hover:bg-neon/90"
          onClick={() => void runSearch()}
          disabled={loading}
        >
          <Search className="size-4" />
          Search
        </Button>
      </div>

      {errorText ? (
        <p className="rounded-md border border-border bg-gunmetal p-3 text-sm text-steel" role="alert">
          {errorText}
        </p>
      ) : null}

      <div aria-live="polite" className="sr-only">
        {loading ? "Searching" : `${results.length} results`}
      </div>

      {loading ? (
        <div className="h-24 animate-pulse rounded-lg bg-gunmetal motion-reduce:animate-none" role="status">
          Searching…
        </div>
      ) : (
        <section className="space-y-2">
          {results.map((item) => (
            <div key={item.sku} className="flex gap-3 rounded-lg border border-border bg-gunmetal p-4">
              <CardThumbnail item={item} />
              <div className="min-w-0 flex-1">
                <p className="font-medium text-foreground">{item.name}</p>
                <p className="font-mono text-xs text-steel">
                  {item.sku} · {item.set_name ?? "—"}
                </p>
                <div className="mt-2 flex flex-wrap gap-4 font-mono text-sm">
                  <span className="font-semibold text-neon">${itemSellPrice(item).toFixed(2)}</span>
                  <Badge variant="outline" className="border-border font-mono text-steel">
                    {item.stock} qty
                  </Badge>
                </div>
              </div>
            </div>
          ))}
          {!loading && query && results.length === 0 && !errorText ? (
            <p className="py-8 text-center font-mono text-sm text-steel">
              No in-stock cards matched. This is an empty result, not a failed write.
            </p>
          ) : null}
        </section>
      )}
    </div>
  );
}

export default function FindPage() {
  return (
    <Suspense fallback={<div className="p-6 font-mono text-sm text-steel">Loading…</div>}>
      <FindInner />
    </Suspense>
  );
}
