"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8000";
const SHOP_ID = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";

export default function ReportsPage() {
  const [trades, setTrades] = useState<Array<Record<string, unknown>>>([]);

  useEffect(() => {
    if (!SHOP_ID) return;
    fetch(`${API}/api/v1/reports/trade-history`, {
      headers: { "X-Shop-Id": SHOP_ID },
    })
      .then((r) => r.json())
      .then((d) => setTrades(d.trades ?? []))
      .catch(() => setTrades([]));
  }, []);

  async function exportCsv() {
    const res = await fetch(`${API}/api/v1/reports/trade-history/export`, {
      headers: { "X-Shop-Id": SHOP_ID },
    });
    const data = await res.json();
    const blob = new Blob([data.csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "trade-history.csv";
    a.click();
  }

  return (
    <div className="p-6">
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-bold">Trade History</h1>
        <Button variant="outline" onClick={exportCsv}>
          Export CSV
        </Button>
      </div>
      {trades.length === 0 ? (
        <p className="text-muted-foreground">No trade transactions yet</p>
      ) : (
        <div className="space-y-2">
          {trades.map((t) => (
            <div key={String(t.id)} className="rounded border p-3 text-sm">
              <span className="font-medium">{String(t.item_name)}</span>
              <span className="ml-2 text-muted-foreground">{String(t.sku)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
