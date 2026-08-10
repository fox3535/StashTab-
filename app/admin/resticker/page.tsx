"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { adminApi } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";

export default function RestickerPage() {
  const [items, setItems] = useState<
    Awaited<ReturnType<typeof adminApi.listRestickerQueue>>
  >([]);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await adminApi.listRestickerQueue());
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function markOne(id: number) {
    try {
      await adminApi.markRestickered(id);
      toast.success("Sticker price updated");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  async function markAll() {
    try {
      const res = await adminApi.markAllRestickered();
      toast.success(`Marked ${res.marked} items restickered`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Needs Restickering</h1>
          <p className="text-muted-foreground">
            Sticker price differs from market by more than your resticker threshold
          </p>
        </div>
        <Button onClick={markAll} disabled={!items.length}>
          Mark all restickered
        </Button>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed py-16 text-center">
          <p className="text-muted-foreground">No items need restickering</p>
        </div>
      ) : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-sm">
            <thead className="border-b bg-muted/50">
              <tr>
                <th className="px-4 py-3 text-left font-medium">SKU</th>
                <th className="px-4 py-3 text-left font-medium">Name</th>
                <th className="px-4 py-3 text-right font-medium">Market</th>
                <th className="px-4 py-3 text-right font-medium">Sticker</th>
                <th className="px-4 py-3 text-right font-medium">New sticker</th>
                <th className="px-4 py-3" />
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.id} className="border-b last:border-0">
                  <td className="px-4 py-3 font-mono text-xs">{item.sku}</td>
                  <td className="px-4 py-3">{item.name}</td>
                  <td className="px-4 py-3 text-right">${item.price.toFixed(2)}</td>
                  <td className="px-4 py-3 text-right">
                    ${(item.sticker_price ?? 0).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right font-medium">
                    ${item.suggested_sticker.toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-right">
                    <Button size="sm" variant="outline" onClick={() => markOne(item.id)}>
                      Restickered
                    </Button>
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
