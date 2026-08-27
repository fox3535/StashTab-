"use client";

import { useEffect, useMemo, useState } from "react";
import { toast } from "sonner";
import { itemSellPrice, mimirApi, type InventoryItem } from "@/lib/mimir-api";
import { adminApi } from "@/lib/admin-api";
import { usePos } from "./pos-context";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";
import { SyncStatusBar } from "./components/sync-status-bar";
import { ApiStatusBar } from "./components/api-status-bar";
import { CardThumbnail } from "./components/card-thumbnail";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
} from "@/components/ui/drawer";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Minus, PackagePlus, Plus, ScanBarcode, ShoppingCart, Trash2 } from "lucide-react";

/* ------------------------------------------------------------------ */
/* Shared cart fragments (used by desktop side panel + mobile drawer)  */
/* ------------------------------------------------------------------ */

function PlaceholderBucket({
  trades,
}: {
  trades: { id: number; total_market_value: number; total_cash_paid: number }[];
}) {
  if (!trades.length) return null;
  return (
    <div className="space-y-2">
      <p className="font-mono text-[10px] uppercase tracking-[0.2em] text-holo-gold/90">
        Placeholder trades · running buckets
      </p>
      {trades.map((t) => (
        <div
          key={t.id}
          className="rounded-md border border-dashed border-holo-gold/50 bg-holo-gold/5 p-3"
        >
          <p className="font-mono text-xs font-semibold text-holo-gold">Placeholder trade</p>
          <p className="mt-0.5 font-mono text-[11px] text-steel">
            Mkt ${t.total_market_value.toFixed(2)} · Cash paid ${t.total_cash_paid.toFixed(2)}
          </p>
        </div>
      ))}
    </div>
  );
}

function CartLine({
  line,
  onQty,
  onRemove,
}: {
  line: InventoryItem & { cartQty: number };
  onQty: (sku: string, qty: number) => void;
  onRemove: (sku: string) => void;
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-obsidian p-3 transition-colors duration-200 hover:border-neon/30">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium text-foreground">{line.name}</p>
        <p className="font-mono text-xs text-steel">
          {line.sku} · ${itemSellPrice(line).toFixed(2)} each
        </p>
      </div>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-steel hover:bg-neon/10 hover:text-neon"
          onClick={() => onQty(line.sku, line.cartQty - 1)}
        >
          <Minus className="h-4 w-4" />
        </Button>
        <span className="w-6 text-center font-mono font-medium text-foreground">
          {line.cartQty}
        </span>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-steel hover:bg-neon/10 hover:text-neon"
          onClick={() => onQty(line.sku, line.cartQty + 1)}
        >
          <Plus className="h-4 w-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-9 w-9 text-destructive/80 hover:bg-destructive/10 hover:text-destructive"
          onClick={() => onRemove(line.sku)}
        >
          <Trash2 className="h-4 w-4" />
        </Button>
      </div>
    </div>
  );
}

function CartTotals({ cartTotal, placeholderCost }: { cartTotal: number; placeholderCost: number }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between">
        <span className="text-sm text-steel">Subtotal</span>
        <span className="font-mono text-2xl font-bold text-foreground">
          ${cartTotal.toFixed(2)}
        </span>
      </div>
      {placeholderCost > 0 && (
        <div className="flex items-center justify-between font-mono text-sm text-holo-gold">
          <span>Placeholder credit</span>
          <span>-${placeholderCost.toFixed(2)}</span>
        </div>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ */
/* Sell page                                                           */
/* ------------------------------------------------------------------ */

export default function SellPage() {
  return (
    <FeatureNotReady
      title="POS checkout and selling"
      detail="Checkout and selling are not ready. Use Find or Inventory for read-only search."
    />
  );
}

function DeferredSellWorkbench() {
  const {
    shopId,
    apiOpts,
    cart,
    addToCart,
    removeFromCart,
    updateCartQty,
    clearCart,
    cartTotal,
    placeholderTrades,
    refreshPlaceholderTrades,
    activeShowId,
  } = usePos();

  const [query, setQuery] = useState("");
  const [game, setGame] = useState("");
  const [tradeRate, setTradeRate] = useState(0.8);
  const [results, setResults] = useState<InventoryItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [cartOpen, setCartOpen] = useState(false);
  const [checkoutOpen, setCheckoutOpen] = useState(false);
  const [tradeModalOpen, setTradeModalOpen] = useState(false);

  const [storeCash, setStoreCash] = useState("");
  const [customerCash, setCustomerCash] = useState("");
  const [amountTendered, setAmountTendered] = useState("");
  const [tradeMarketValue, setTradeMarketValue] = useState("");
  const [tradeCashPaid, setTradeCashPaid] = useState("");

  const placeholderCost = useMemo(
    () =>
      placeholderTrades.reduce((sum, t) => {
        const paid =
          t.total_cash_paid > 0
            ? t.total_cash_paid
            : t.total_market_value * tradeRate;
        return sum + paid;
      }, 0),
    [placeholderTrades, tradeRate]
  );

  const netDue = useMemo(() => {
    const store = parseFloat(storeCash) || 0;
    const cust = parseFloat(customerCash) || 0;
    return cartTotal - placeholderCost + store - cust;
  }, [cartTotal, placeholderCost, storeCash, customerCash]);

  const changeDue = useMemo(() => {
    const tendered = parseFloat(amountTendered) || 0;
    return Math.max(0, tendered - cartTotal);
  }, [amountTendered, cartTotal]);

  useEffect(() => {
    if (shopId) refreshPlaceholderTrades();
  }, [shopId, refreshPlaceholderTrades]);

  useEffect(() => {
    adminApi
      .getSettings()
      .then((s) => {
        if (s.trade_percentage) setTradeRate(s.trade_percentage);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!shopId) return;
    runSearch("");
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId, game]);

  async function runSearch(searchQuery?: string) {
    const q = (searchQuery ?? query).trim();
    if (!shopId) {
      toast.error("Set NEXT_PUBLIC_DEV_SHOP_ID in .env.local");
      return;
    }
    setLoading(true);
    try {
      const data = await mimirApi.searchInventory(q, {
        ...apiOpts,
        limit: 20,
        game: game || undefined,
      });
      setResults(data.items);
      if (data.items.length === 1 && q.length >= 4) {
        addToCart(data.items[0]);
        setQuery("");
        toast.success(`Added ${data.items[0].name}`);
      }
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Search failed");
    } finally {
      setLoading(false);
    }
  }

  async function checkoutCash() {
    if (!cart.length) return;
    setLoading(true);
    try {
      const res = await mimirApi.checkout(
        {
          lines: cart.map((l) => ({ sku: l.sku, quantity: l.cartQty })),
          payment_method: "cash",
          amount_tendered: parseFloat(amountTendered) || undefined,
          show_session_id: activeShowId ?? undefined,
        },
        apiOpts
      );
      toast.success(
        `Sale complete — $${res.total.toFixed(2)}${res.change_due > 0 ? ` · Change $${res.change_due.toFixed(2)}` : ""}`
      );
      clearCart();
      setResults([]);
      setCheckoutOpen(false);
      setCartOpen(false);
      setAmountTendered("");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Checkout failed");
    } finally {
      setLoading(false);
    }
  }

  async function checkoutTrade() {
    if (!cart.length && !placeholderTrades.length) {
      toast.error("Add items or placeholder trades first");
      return;
    }
    setLoading(true);
    try {
      const res = await mimirApi.checkout(
        {
          lines: cart.map((l) => ({ sku: l.sku, quantity: l.cartQty })),
          payment_method: "trade",
          placeholder_cost: placeholderCost,
          store_cash: parseFloat(storeCash) || 0,
          customer_cash: parseFloat(customerCash) || 0,
          final_sale_price: netDue,
          clear_placeholder_trades: true,
          show_session_id: activeShowId ?? undefined,
        },
        apiOpts
      );
      toast.success(`Trade complete — Net $${res.net_due.toFixed(2)}`);
      clearCart();
      setResults([]);
      setCheckoutOpen(false);
      setCartOpen(false);
      setStoreCash("");
      setCustomerCash("");
      await refreshPlaceholderTrades();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Trade checkout failed");
    } finally {
      setLoading(false);
    }
  }

  async function checkoutCard() {
    if (!cart.length) return;
    setLoading(true);
    try {
      const res = await mimirApi.checkout(
        {
          lines: cart.map((l) => ({ sku: l.sku, quantity: l.cartQty })),
          payment_method: "card",
          show_session_id: activeShowId ?? undefined,
        },
        apiOpts
      );
      toast.success(`Card sale complete — $${res.total.toFixed(2)}`);
      clearCart();
      setResults([]);
      setCheckoutOpen(false);
      setCartOpen(false);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Card checkout failed");
    } finally {
      setLoading(false);
    }
  }

  async function submitPlaceholderTrade() {
    const market = parseFloat(tradeMarketValue) || 0;
    const cash = parseFloat(tradeCashPaid) || 0;
    if (market <= 0) {
      toast.error("Enter market value");
      return;
    }
    try {
      await mimirApi.addPlaceholderTrade(
        { market_value: market, cash_paid: cash },
        apiOpts
      );
      toast.success("Placeholder trade added");
      setTradeMarketValue("");
      setTradeCashPaid("");
      setTradeModalOpen(false);
      await refreshPlaceholderTrades();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to add trade");
    }
  }

  const cartCount = cart.reduce((n, l) => n + l.cartQty, 0);

  const openCheckout = () => {
    setCartOpen(false);
    setCheckoutOpen(true);
  };

  /* ------------------------- scan / results column ------------------------- */
  const scanColumn = (
    <div className="flex min-w-0 flex-1 flex-col gap-3">
      <ApiStatusBar />
      <SyncStatusBar />

      <div className="flex gap-2">
        <select
          className="min-h-12 rounded-md border border-border bg-surface px-3 font-mono text-sm text-foreground outline-none transition-colors duration-200 focus:border-neon"
          value={game}
          onChange={(e) => setGame(e.target.value)}
          aria-label="Game filter"
        >
          <option value="">All games</option>
          <option value="Pokemon">Pokemon</option>
          <option value="One Piece">One Piece</option>
          <option value="Magic">Magic</option>
        </select>
        <div className="relative min-w-0 flex-1">
          <ScanBarcode className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-steel" />
          <Input
            className="min-h-12 border-border bg-surface pl-9 font-mono text-sm tracking-wide focus-visible:border-neon focus-visible:shadow-[0_0_18px_rgba(139,92,246,0.3)]"
            placeholder="Scan barcode / SKU or search…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") runSearch();
            }}
            autoComplete="off"
          />
        </div>
        <Button
          className="min-h-12 min-w-16 bg-neon font-display font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
          onClick={() => runSearch()}
          disabled={loading}
        >
          Find
        </Button>
      </div>

      <section className="space-y-2">
        {results.map((item) => (
          <button
            key={item.sku}
            type="button"
            className="flex w-full items-center gap-3 rounded-lg border border-border bg-gunmetal px-4 py-3 text-left transition-all duration-200 hover:border-neon/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.12)] active:bg-surface"
            onClick={() => {
              addToCart(item);
              toast.success(`Added ${item.name}`);
            }}
          >
            <CardThumbnail item={item} />
            <div className="min-w-0 flex-1 pr-3">
              <p className="truncate font-medium text-foreground">{item.name}</p>
              <p className="font-mono text-xs text-steel">
                {item.sku} · {item.game} · {item.stock} in stock
              </p>
            </div>
            <p className="shrink-0 font-mono text-lg font-semibold text-neon">
              ${itemSellPrice(item).toFixed(2)}
            </p>
          </button>
        ))}
        {!loading && query && results.length === 0 && (
          <p className="py-8 text-center font-mono text-sm text-steel">No matches</p>
        )}
      </section>
    </div>
  );

  /* --------------------------- live cart column --------------------------- */
  const cartColumn = (
    <div className="flex h-full flex-col gap-3">
      <div className="flex items-center justify-between">
        <h2 className="font-display text-sm font-bold uppercase tracking-[0.18em] text-foreground">
          Live Cart
        </h2>
        <span className="font-mono text-xs text-steel">{cartCount} items</span>
      </div>

      <div className="scrollbar-slim min-h-0 flex-1 space-y-2 overflow-y-auto pr-1">
        <PlaceholderBucket trades={placeholderTrades} />
        {cart.map((line) => (
          <CartLine key={line.sku} line={line} onQty={updateCartQty} onRemove={removeFromCart} />
        ))}
        {!cart.length && !placeholderTrades.length && (
          <div className="flex h-40 flex-col items-center justify-center gap-2 rounded-md border border-dashed border-border text-steel">
            <ShoppingCart className="size-6 opacity-50" />
            <p className="font-mono text-xs">Scan to start a sale</p>
          </div>
        )}
      </div>

      <div className="space-y-3 border-t border-border pt-3">
        <CartTotals cartTotal={cartTotal} placeholderCost={placeholderCost} />
        <Button
          variant="outline"
          className="w-full border-holo-gold/40 bg-holo-gold/5 font-mono text-xs text-holo-gold transition-all duration-200 hover:border-holo-gold/70 hover:bg-holo-gold/10"
          onClick={() => setTradeModalOpen(true)}
        >
          <PackagePlus className="size-4" />
          Add placeholder trade
        </Button>
        <Button
          className="h-13 w-full bg-neon font-display text-base font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_24px_rgba(139,92,246,0.5)]"
          disabled={!cart.length && !placeholderTrades.length}
          onClick={openCheckout}
        >
          Checkout
        </Button>
      </div>
    </div>
  );

  return (
    <div className="flex flex-1 flex-col pt-[max(0rem,env(safe-area-inset-top))] lg:flex-row">
      {/* Desktop split: live cart left, scanning right */}
      <aside className="hidden w-[380px] shrink-0 border-r border-border bg-gunmetal p-5 lg:block">
        {cartColumn}
      </aside>

      <main className="flex min-w-0 flex-1 flex-col gap-3 p-4 md:p-6 lg:p-8">
        <header className="lg:hidden">
          <h1 className="font-display text-xl font-bold tracking-tight text-foreground">
            Stash<span className="text-neon">Tab</span>
          </h1>
          <p className="text-sm text-steel">Show-floor checkout</p>
        </header>

        {scanColumn}
      </main>

      {/* Mobile cart drawer trigger */}
      <Drawer open={cartOpen} onOpenChange={setCartOpen}>
        <DrawerTrigger asChild>
          <Button
            className="fixed bottom-6 right-4 z-40 h-14 w-14 rounded-full bg-neon text-white shadow-lg shadow-black/50 transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_24px_rgba(139,92,246,0.55)] lg:hidden"
            size="icon"
          >
            <ShoppingCart className="h-6 w-6" />
            {cartCount > 0 && (
              <span className="absolute -right-1 -top-1 flex h-5 w-5 items-center justify-center rounded-full bg-obsidian font-mono text-xs font-bold text-neon">
                {cartCount}
              </span>
            )}
          </Button>
        </DrawerTrigger>
        <DrawerContent className="glass-panel border-border text-foreground">
          <DrawerHeader>
            <DrawerTitle className="font-display">Cart ({cartCount} items)</DrawerTitle>
          </DrawerHeader>
          <div className="max-h-[50vh] space-y-2 overflow-y-auto px-4">
            <PlaceholderBucket trades={placeholderTrades} />
            {cart.map((line) => (
              <CartLine key={line.sku} line={line} onQty={updateCartQty} onRemove={removeFromCart} />
            ))}
          </div>
          <DrawerFooter className="border-t border-border">
            <CartTotals cartTotal={cartTotal} placeholderCost={placeholderCost} />
            <div className="grid grid-cols-2 gap-2">
              <Button
                variant="outline"
                className="min-h-12 border-holo-gold/40 bg-holo-gold/5 font-mono text-xs text-holo-gold hover:bg-holo-gold/10"
                onClick={() => setTradeModalOpen(true)}
              >
                + Trade
              </Button>
              <Button
                className="min-h-12 bg-neon font-display font-bold text-white hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
                disabled={!cart.length && !placeholderTrades.length}
                onClick={openCheckout}
              >
                Checkout
              </Button>
            </div>
            <DrawerClose asChild>
              <Button variant="ghost" className="min-h-12 text-steel">
                Close
              </Button>
            </DrawerClose>
          </DrawerFooter>
        </DrawerContent>
      </Drawer>

      {/* Checkout sheet */}
      <Sheet open={checkoutOpen} onOpenChange={setCheckoutOpen}>
        <SheetContent
          side="bottom"
          className="glass-panel max-h-[90vh] overflow-y-auto border-border text-foreground"
        >
          <SheetHeader>
            <SheetTitle className="font-display">Settlement</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div className="rounded-lg border border-border bg-obsidian p-4">
              <div className="flex justify-between font-display text-lg font-semibold">
                <span>Total</span>
                <span className="font-mono text-neon">${cartTotal.toFixed(2)}</span>
              </div>
            </div>

            <div className="space-y-3 rounded-lg border border-border bg-obsidian p-4">
              <p className="font-mono text-xs font-medium uppercase tracking-[0.18em] text-neon">
                Cash settlement
              </p>
              <div>
                <Label htmlFor="tendered" className="text-steel">
                  Amount tendered
                </Label>
                <Input
                  id="tendered"
                  type="number"
                  inputMode="decimal"
                  step="0.01"
                  className="mt-1 min-h-12 border-border bg-surface font-mono focus-visible:border-neon"
                  placeholder="0.00"
                  value={amountTendered}
                  onChange={(e) => setAmountTendered(e.target.value)}
                />
              </div>
              {parseFloat(amountTendered) > 0 && (
                <p className="font-mono text-lg font-semibold text-emerald-400">
                  Change due: ${changeDue.toFixed(2)}
                </p>
              )}
              <Button
                className="min-h-12 w-full bg-neon font-display font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
                disabled={loading || !cart.length}
                onClick={checkoutCash}
              >
                Cash Checkout
              </Button>
            </div>

            <div className="space-y-3 rounded-lg border border-holo-gold/30 bg-obsidian p-4">
              <p className="font-mono text-xs font-medium uppercase tracking-[0.18em] text-holo-gold">
                Trade settlement
              </p>
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <Label className="text-steel">Store cash out</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    className="mt-1 min-h-12 border-border bg-surface font-mono focus-visible:border-holo-gold/60"
                    value={storeCash}
                    onChange={(e) => setStoreCash(e.target.value)}
                  />
                </div>
                <div>
                  <Label className="text-steel">Customer cash in</Label>
                  <Input
                    type="number"
                    inputMode="decimal"
                    step="0.01"
                    className="mt-1 min-h-12 border-border bg-surface font-mono focus-visible:border-holo-gold/60"
                    value={customerCash}
                    onChange={(e) => setCustomerCash(e.target.value)}
                  />
                </div>
              </div>
              <p className="font-display text-lg font-semibold">
                Net due:{" "}
                <span className="font-mono text-holo-gold">${netDue.toFixed(2)}</span>
              </p>
              <Button
                variant="outline"
                className="min-h-12 w-full border-holo-gold/50 font-mono text-holo-gold transition-all duration-200 hover:bg-holo-gold/10"
                disabled={loading}
                onClick={checkoutTrade}
              >
                Trade Checkout
              </Button>
            </div>

            <div className="space-y-3 rounded-lg border border-holo-pink/30 bg-obsidian p-4">
              <p className="font-mono text-xs font-medium uppercase tracking-[0.18em] text-holo-pink">
                Card payment
              </p>
              <p className="font-mono text-xs text-steel">
                Records sale with card processing fees (2.6% + $0.10 per transaction).
              </p>
              <Button
                className="min-h-12 w-full bg-holo-pink font-display font-bold text-white transition-all duration-200 hover:bg-holo-pink/90 hover:shadow-[0_0_20px_rgba(168,85,247,0.4)]"
                disabled={loading || !cart.length}
                onClick={checkoutCard}
              >
                Card Checkout
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>

      {/* Placeholder trade sheet */}
      <Sheet open={tradeModalOpen} onOpenChange={setTradeModalOpen}>
        <SheetContent
          side="bottom"
          className="glass-panel border-border text-foreground"
        >
          <SheetHeader>
            <SheetTitle className="font-display">Placeholder Trade</SheetTitle>
          </SheetHeader>
          <div className="mt-4 space-y-4">
            <div className="rounded-md border border-dashed border-holo-gold/40 bg-holo-gold/5 p-3">
              <p className="font-mono text-[11px] leading-relaxed text-steel">
                Running-total bucket for bulk show acquisitions. Cost basis is distributed by
                market-value weight at staging.
              </p>
            </div>
            <div>
              <Label className="text-steel">Incoming card market value</Label>
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                className="mt-1 min-h-12 border-border bg-surface font-mono focus-visible:border-holo-gold/60"
                value={tradeMarketValue}
                onChange={(e) => setTradeMarketValue(e.target.value)}
              />
            </div>
            <div>
              <Label className="text-steel">Cash paid to customer</Label>
              <Input
                type="number"
                inputMode="decimal"
                step="0.01"
                className="mt-1 min-h-12 border-border bg-surface font-mono focus-visible:border-holo-gold/60"
                value={tradeCashPaid}
                onChange={(e) => setTradeCashPaid(e.target.value)}
              />
            </div>
            <Button
              className="min-h-12 w-full bg-holo-gold font-display font-bold text-white transition-all duration-200 hover:bg-holo-gold/90 hover:shadow-[0_0_20px_rgba(124,58,237,0.35)]"
              onClick={submitPlaceholderTrade}
            >
              Add to trade queue
            </Button>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}
