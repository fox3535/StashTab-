"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { toast } from "sonner";
import { itemSellPrice, mimirApi, type InventoryItem } from "@/lib/mimir-api";
import { usePos } from "../pos-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { CardThumbnail } from "../components/card-thumbnail";
import { Search } from "lucide-react";

function FindInner() {
  const searchParams = useSearchParams();
  const initialQ = searchParams.get("q") ?? "";

  const { shopId, apiOpts } = usePos();
  const [query, setQuery] = useState(initialQ);
  const [game, setGame] = useState<string>("");
  const [results, setResults] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);

  async function runSearch(q?: string) {
    if (!shopId) {
      toast.error("Set NEXT_PUBLIC_DEV_SHOP_ID");
      return;
    }
    setLoading(true);
    try {
      const data = await mimirApi.searchInventory(q ?? query, {
        ...apiOpts,
        game: game || undefined,
        limit: 50,
      });
      setResults(data.items);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  // Auto-run when arriving from the global header scan bar
  useEffect(() => {
    if (initialQ) {
      setQuery(initialQ);
      runSearch(initialQ);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialQ]);

  return (
    <div className="flex flex-col gap-4 p-4 pt-[max(1rem,env(safe-area-inset-top))] md:p-6 lg:p-8">
      <header>
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">Find</h1>
        <p className="text-sm text-steel">
          Booth lookup — stock and prices only. Edit vault in Admin → Inventory.
        </p>
      </header>

      <div className="flex gap-2">
        <Input
          className="min-h-12 border-border bg-surface font-mono text-sm focus-visible:border-neon focus-visible:shadow-[0_0_16px_rgba(139,92,246,0.25)]"
          placeholder="Scan barcode or search SKU..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && runSearch()}
        />
        <Button
          className="min-h-12 bg-neon font-display font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
          onClick={() => runSearch()}
          disabled={loading}
        >
          <Search className="size-4" />
          Search
        </Button>
      </div>

      <div className="flex gap-2">
        {["", "Pokemon", "One Piece", "Magic"].map((g) => (
          <Button
            key={g || "all"}
            size="sm"
            variant={game === g ? "default" : "outline"}
            className={
              game === g
                ? "border-neon/50 bg-neon/15 font-mono text-xs text-neon shadow-[0_0_12px_rgba(139,92,246,0.2)] hover:bg-neon/20"
                : "border-border bg-gunmetal text-steel transition-colors duration-200 hover:border-neon/40 hover:text-neon"
            }
            onClick={() => setGame(g)}
          >
            {g || "All"}
          </Button>
        ))}
      </div>

      <section className="space-y-2">
        {results.map((item) => (
          <div
            key={item.sku}
            className="flex gap-3 rounded-lg border border-border bg-gunmetal p-4 transition-all duration-200 hover:border-neon/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.12)]"
          >
            <CardThumbnail item={item} />
            <div className="min-w-0 flex-1">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-foreground">{item.name}</p>
                  <p className="font-mono text-xs text-steel">
                    {item.sku} · {item.set_name ?? "—"}
                  </p>
                </div>
                <Badge
                  variant="outline"
                  className="border-border bg-surface font-mono text-steel"
                >
                  {item.stock} qty
                </Badge>
              </div>
              <div className="mt-2 flex gap-4 font-mono text-sm">
                <span className="font-semibold text-neon">
                  Sell ${itemSellPrice(item).toFixed(2)}
                </span>
                <span className="text-steel">Mkt ${item.price.toFixed(2)}</span>
                <span className="text-steel/70">{item.game}</span>
              </div>
            </div>
          </div>
        ))}
        {!loading && query && results.length === 0 && (
          <p className="py-8 text-center font-mono text-sm text-steel">No matches in the vault</p>
        )}
      </section>
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
