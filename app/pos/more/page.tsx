"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { mimirApi, type SaleRecord } from "@/lib/mimir-api";
import { usePos } from "../pos-context";
import { SyncStatusBar } from "../components/sync-status-bar";

export default function MorePage() {
  const { shopId, apiOpts } = usePos();
  const [sales, setSales] = useState<SaleRecord[]>([]);

  useEffect(() => {
    if (!shopId) return;
    mimirApi.salesHistory({ ...apiOpts, limit: 10 }).then((data) => {
      setSales(data.sales);
    }).catch(() => setSales([]));
  }, [shopId, apiOpts]);

  return (
    <div className="flex flex-col gap-4 p-4 pt-[max(1rem,env(safe-area-inset-top))] md:p-6 lg:p-8">
      <header>
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">More</h1>
        <p className="text-sm text-steel">Settings & history</p>
      </header>

      <SyncStatusBar />

      <div className="space-y-2">
        <Link
          href="/admin/dashboard"
          className="block rounded-lg border border-border bg-gunmetal px-4 py-3 text-sm text-foreground transition-all duration-200 hover:border-neon/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.12)]"
        >
          Admin Dashboard →
        </Link>
        <Link
          href="/onboarding"
          className="block rounded-lg border border-border bg-gunmetal px-4 py-3 text-sm text-foreground transition-all duration-200 hover:border-neon/40 hover:shadow-[0_0_16px_rgba(139,92,246,0.12)]"
        >
          Shop Setup →
        </Link>
      </div>

      <section>
        <p className="mb-2 font-mono text-xs font-medium uppercase tracking-[0.18em] text-steel">Recent sales</p>
        {sales.length === 0 ? (
          <p className="text-sm text-steel/70">No sales yet</p>
        ) : (
          <div className="space-y-2">
            {sales.map((sale) => (
              <div
                key={sale.id}
                className="rounded-lg border border-border bg-gunmetal px-3 py-2 text-sm"
              >
                <div className="flex justify-between">
                  <span className="truncate font-medium text-foreground">{sale.item_name}</span>
                  <span className="font-mono font-semibold text-neon">
                    ${(sale.sold_price ?? 0).toFixed(2)}
                  </span>
                </div>
                <p className="font-mono text-xs text-steel">
                  {sale.sku} · {sale.transaction_type}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>

      <p className="text-center font-mono text-xs text-steel/60">
        StashTab · Dev shop {shopId ? shopId.slice(0, 8) + "…" : "not set"}
      </p>
    </div>
  );
}
