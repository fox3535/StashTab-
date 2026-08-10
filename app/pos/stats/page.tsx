"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { mimirApi, type ShowSession } from "@/lib/mimir-api";
import { usePos } from "../pos-context";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type PnL = {
  show_id: string;
  name: string;
  total_revenue: number;
  total_profit: number;
  sale_count: number;
};

export default function StatsPage() {
  const { shopId, apiOpts, activeShowId, setActiveShowId } = usePos();
  const [shows, setShows] = useState<ShowSession[]>([]);
  const [showName, setShowName] = useState("");
  const [pnl, setPnl] = useState<PnL | null>(null);
  const [loading, setLoading] = useState(false);

  async function loadShows() {
    if (!shopId) return;
    try {
      const data = await mimirApi.listShowSessions(apiOpts);
      setShows(data);
      const active = data.find((s) => s.status === "active");
      if (active) setActiveShowId(active.id);
    } catch {
      setShows([]);
    }
  }

  async function startShow() {
    if (!showName.trim()) {
      toast.error("Enter a show name");
      return;
    }
    setLoading(true);
    try {
      const session = await mimirApi.startShow(showName.trim(), apiOpts);
      setActiveShowId(session.id);
      setShowName("");
      toast.success(`Show started: ${session.name}`);
      await loadShows();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to start show");
    } finally {
      setLoading(false);
    }
  }

  async function endShow(id: string) {
    setLoading(true);
    try {
      await mimirApi.endShow(id, apiOpts);
      if (activeShowId === id) setActiveShowId(null);
      toast.success("Show ended");
      await loadShows();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to end show");
    } finally {
      setLoading(false);
    }
  }

  async function loadPnL(id: string) {
    try {
      const data = await mimirApi.showPnL(id, apiOpts);
      setPnl(data);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load P&L");
    }
  }

  async function captureShowPrices() {
    setLoading(true);
    try {
      const res = await mimirApi.captureShowPrices(apiOpts);
      toast.success(res.message);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Capture failed");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadShows();
  }, [shopId]);

  const activeShow = shows.find((s) => s.status === "active");

  return (
    <div className="flex flex-col gap-4 p-4 pt-[max(1rem,env(safe-area-inset-top))] md:p-6 lg:p-8">
      <header>
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">Stats</h1>
        <p className="text-sm text-steel">Show mode & P&L</p>
      </header>

      {activeShow ? (
        <div className="rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-4">
          <p className="font-mono text-xs uppercase tracking-[0.18em] text-emerald-400">Active show</p>
          <p className="mt-1 font-display text-lg font-semibold text-foreground">{activeShow.name}</p>
          <div className="mt-3 flex gap-2">
            <Button
              variant="outline"
              className="min-h-10 border-border bg-gunmetal text-steel transition-colors duration-200 hover:border-neon/50 hover:text-neon"
              onClick={() => loadPnL(activeShow.id)}
            >
              View P&L
            </Button>
            <Button
              className="min-h-10 bg-destructive/80 hover:bg-destructive"
              disabled={loading}
              onClick={() => endShow(activeShow.id)}
            >
              End Show
            </Button>
          </div>
        </div>
      ) : (
        <div className="space-y-3 rounded-lg border border-border bg-gunmetal p-4">
          <p className="text-sm text-steel">Start a new show session</p>
          <Input
            className="min-h-12 border-border bg-surface"
            placeholder="Show name (e.g. Columbus Comic Con)"
            value={showName}
            onChange={(e) => setShowName(e.target.value)}
          />
          <Button
            className="min-h-12 w-full bg-neon font-display font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
            disabled={loading}
            onClick={startShow}
          >
            Start Show
          </Button>
        </div>
      )}

      <div className="rounded-lg border border-border bg-gunmetal p-4">
        <p className="text-sm text-steel">Round all in-stock prices up to sticker prices for the show floor</p>
        <Button
          className="mt-3 min-h-10 w-full bg-surface text-foreground transition-colors duration-200 hover:bg-neon/10 hover:text-neon"
          disabled={loading}
          onClick={captureShowPrices}
        >
          Capture Show Prices
        </Button>
      </div>

      {pnl && (
        <div className="rounded-lg border border-border bg-gunmetal p-4">
          <p className="font-medium text-foreground">{pnl.name}</p>
          <div className="mt-3 grid grid-cols-3 gap-2 text-center">
            <div>
              <p className="font-mono text-xs uppercase tracking-wider text-steel">Revenue</p>
              <p className="font-mono text-lg font-bold text-neon">
                ${pnl.total_revenue.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="font-mono text-xs uppercase tracking-wider text-steel">Profit</p>
              <p className="font-mono text-lg font-bold text-emerald-400">
                ${pnl.total_profit.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="font-mono text-xs uppercase tracking-wider text-steel">Sales</p>
              <p className="font-mono text-lg font-bold text-foreground">{pnl.sale_count}</p>
            </div>
          </div>
        </div>
      )}

      {shows.length > 0 && (
        <section>
          <p className="mb-2 font-mono text-xs uppercase tracking-[0.18em] text-steel">Recent shows</p>
          <div className="space-y-2">
            {shows.slice(0, 5).map((s) => (
              <button
                key={s.id}
                type="button"
                className="flex w-full items-center justify-between rounded-lg border border-border bg-gunmetal px-3 py-2 text-left text-sm transition-all duration-200 hover:border-neon/40"
                onClick={() => loadPnL(s.id)}
              >
                <span className="text-foreground">{s.name}</span>
                <span className="font-mono text-xs text-steel">{s.status}</span>
              </button>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
