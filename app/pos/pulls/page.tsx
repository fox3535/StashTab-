"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { mimirApi, type PullQueueItem } from "@/lib/mimir-api";
import { usePos } from "../pos-context";
import { Button } from "@/components/ui/button";

export default function PullsPage() {
  const { shopId, apiOpts } = usePos();
  const [pulls, setPulls] = useState<PullQueueItem[]>([]);
  const [loading, setLoading] = useState(true);

  async function loadPulls() {
    if (!shopId) return;
    setLoading(true);
    try {
      const data = await mimirApi.listPulls(apiOpts);
      setPulls(data);
    } catch {
      setPulls([]);
    } finally {
      setLoading(false);
    }
  }

  async function markPulled(id: number) {
    try {
      await mimirApi.markPulled(id, apiOpts);
      toast.success("Marked as pulled");
      await loadPulls();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  useEffect(() => {
    loadPulls();
  }, [shopId]);

  return (
    <div className="flex flex-col gap-3 p-4 md:p-6 lg:p-8 pt-[max(1rem,env(safe-area-inset-top))]">
      <header>
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">Pulls</h1>
        <p className="text-sm text-steel">Online orders to pull</p>
      </header>

      {loading ? (
        <p className="text-center font-mono text-sm text-steel">Loading…</p>
      ) : pulls.length === 0 ? (
        <div className="rounded-xl border border-dashed border-border py-12 text-center">
          <p className="text-sm text-steel">No pending pulls</p>
          <p className="mt-1 font-mono text-xs text-steel/60">
            Shopify orders will appear here after sync
          </p>
        </div>
      ) : (
        <section className="space-y-2">
          {pulls.map((pull) => (
            <div
              key={pull.id}
              className="flex items-center justify-between rounded-xl border border-border bg-gunmetal p-4 transition-all duration-200 hover:border-neon/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.12)]"
            >
              <div>
                <p className="font-mono text-sm font-medium text-foreground">{pull.sku}</p>
                <p className="font-mono text-xs text-steel">
                  Order {pull.order_id ?? "—"}
                </p>
              </div>
              <Button
                size="sm"
                className="min-h-10 bg-neon font-display font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_18px_rgba(139,92,246,0.45)]"
                onClick={() => markPulled(pull.id)}
              >
                Pulled
              </Button>
            </div>
          ))}
        </section>
      )}
    </div>
  );
}
