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
import {
  FIND_PAGE_SIZE,
  classifyFindResponse,
  findPageWindow,
  offsetForPage,
  pageAfterReset,
} from "@/lib/pos-find";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { CardThumbnail } from "../components/card-thumbnail";

function ResultCard({ item, exact }: { item: InventoryItem; exact?: boolean }) {
  return (
    <div className="flex gap-3 rounded-lg border border-border bg-gunmetal p-4">
      <CardThumbnail item={item} />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-2">
          <p className="font-medium text-foreground">{item.name}</p>
          {exact ? (
            <Badge className="border-neon/40 bg-neon/10 font-mono text-neon">
              Exact SKU/barcode match
            </Badge>
          ) : null}
        </div>
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
  );
}

function FindInner() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);
  const [query, setQuery] = useState(initialQ);
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [results, setResults] = useState<InventoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  async function runSearch(q: string, targetPage: number, signal?: AbortSignal) {
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
      setResults(data.items ?? []);
      setTotal(typeof data.total === "number" ? data.total : data.items?.length ?? 0);
      setPage(targetPage);
      setSubmittedQuery(q);
    } catch (err) {
      if (signal?.aborted) return;
      if (myEpoch !== epochRef.current) return;
      if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
      const classified = classifyVendorError(err);
      reportApiError(err);
      setResults([]);
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
  }

  function submitSearch() {
    void runSearch(query, pageAfterReset());
  }

  useEffect(() => {
    const controller = new AbortController();
    setResults([]);
    setTotal(0);
    setPage(pageAfterReset());
    setErrorText("");
    if (shopId && (initialQ || query)) void runSearch(initialQ || query, pageAfterReset(), controller.signal);
    else setLoading(false);
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQ, shopId]);

  const mode = classifyFindResponse(submittedQuery, total, results[0]?.sku);
  const windowInfo = findPageWindow(total, offsetForPage(page, FIND_PAGE_SIZE), FIND_PAGE_SIZE);
  const hasSearched = submittedQuery.trim().length > 0 && !errorText;

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
          onKeyDown={(e) => e.key === "Enter" && submitSearch()}
          aria-label="Search inventory"
        />
        <Button
          className="min-h-12 bg-neon font-display font-bold text-white hover:bg-neon/90"
          onClick={submitSearch}
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
        {loading ? "Searching" : `${results.length} results on this page`}
      </div>

      {hasSearched && !loading ? (
        <p className="font-mono text-sm text-steel" role="status">
          {total} in-stock {total === 1 ? "match" : "matches"}.
        </p>
      ) : null}

      {loading ? (
        <div className="h-24 animate-pulse rounded-lg bg-gunmetal motion-reduce:animate-none" role="status">
          Searching…
        </div>
      ) : (
        <section className="space-y-2" aria-label="Search results">
          {mode === "exact" && results[0] ? (
            <ResultCard item={results[0]} exact />
          ) : (
            results.map((item) => <ResultCard key={item.sku} item={item} />)
          )}
          {!loading && submittedQuery && results.length === 0 && !errorText ? (
            <p className="py-8 text-center font-mono text-sm text-steel">
              No in-stock cards matched. This is an empty result, not a failed write.
            </p>
          ) : null}
        </section>
      )}

      {hasSearched && mode === "list" && total > 0 && !loading ? (
        <nav aria-label="Result pages" className="flex flex-wrap items-center gap-3">
          <Button
            variant="outline"
            className="min-h-12 border-border font-mono text-sm"
            onClick={() => void runSearch(submittedQuery, page - 1)}
            disabled={!windowInfo.hasPrev || loading}
            aria-label="Previous results page"
          >
            ← Previous
          </Button>
          <span className="font-mono text-sm text-steel">
            {windowInfo.from}–{windowInfo.to} of {total}
          </span>
          <Button
            variant="outline"
            className="min-h-12 border-border font-mono text-sm"
            onClick={() => void runSearch(submittedQuery, page + 1)}
            disabled={!windowInfo.hasNext || loading}
            aria-label="Next results page"
          >
            Next →
          </Button>
          {windowInfo.endOfResults ? (
            <span className="font-mono text-xs text-steel/80">End of results.</span>
          ) : null}
        </nav>
      ) : null}
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
