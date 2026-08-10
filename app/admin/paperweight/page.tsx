"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { adminApi } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";

export default function PaperweightPage() {
  const [units, setUnits] = useState(0);
  const [items, setItems] = useState<
    Awaited<ReturnType<typeof adminApi.listPaperweight>>["items"]
  >([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminApi.listPaperweight();
      setUnits(data.units);
      setItems(data.items);
    } catch {
      setItems([]);
      setUnits(0);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Paperweight Alert</h1>
          <p className="text-muted-foreground">
            Stock sitting {units > 0 ? "" : ""}60+ days (configurable) — discount
            to recover liquidity
          </p>
        </div>
        <div className="flex gap-2">
          <Link href="/admin/settings">
            <Button variant="outline">Threshold settings</Button>
          </Link>
          <Button variant="outline" onClick={load}>
            Refresh
          </Button>
        </div>
      </div>

      <p className="mb-4 text-sm font-medium text-destructive">
        {units} stagnant units
      </p>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed py-16 text-center text-muted-foreground">
          No paperweight inventory — vault is turning over
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left">SKU</th>
                <th className="px-4 py-3 text-left">Name</th>
                <th className="px-4 py-3 text-right">Stock</th>
                <th className="px-4 py-3 text-right">Price</th>
                <th className="px-4 py-3 text-left">Date added</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">{item.sku}</td>
                  <td className="px-4 py-3">{item.name}</td>
                  <td className="px-4 py-3 text-right">{item.stock}</td>
                  <td className="px-4 py-3 text-right">
                    ${item.price.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-muted-foreground">
                    {item.date_added
                      ? new Date(item.date_added).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
