"use client";

import { useCallback, useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { toast } from "sonner";
import { adminApi, type StagingItem } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";

type PendingTrade = {
  id: number;
  total_market_value: number;
  total_cash_paid: number;
};

export default function AdminStagingPage() {
  const [items, setItems] = useState<StagingItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [tradesOpen, setTradesOpen] = useState(false);
  const [trades, setTrades] = useState<PendingTrade[]>([]);
  const [selectedTradeIds, setSelectedTradeIds] = useState<number[]>([]);
  const [applying, setApplying] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await adminApi.listStaging());
    } catch {
      setItems([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function commitOne(id: number) {
    try {
      const res = await adminApi.commitStaging(id);
      toast.success(`Committed ${res.name} (${res.sku})`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Commit failed");
    }
  }

  async function refetchOne(item: StagingItem) {
    try {
      await adminApi.refetchStaging(item.id, {
        name: item.name,
        set_name: item.set_name ?? undefined,
        sequence_number: item.sequence_number ?? undefined,
      });
      toast.success(`Re-fetched ${item.name}`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Refetch failed");
    }
  }

  async function deleteOne(id: number) {
    try {
      await adminApi.deleteStaging(id);
      toast.success("Removed from staging");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Delete failed");
    }
  }

  async function commitAll() {
    try {
      const res = await adminApi.commitAllStaging();
      toast.success(`Committed ${res.committed} items to inventory`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Commit failed");
    }
  }

  async function openApplyTrades() {
    try {
      const pending = await adminApi.listPendingTrades();
      if (!pending.length) {
        toast.error("No pending trades from POS");
        return;
      }
      setTrades(pending);
      setSelectedTradeIds(pending.map((t) => t.id));
      setTradesOpen(true);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to load trades");
    }
  }

  async function applyTrades() {
    if (!selectedTradeIds.length) {
      toast.error("Select at least one trade");
      return;
    }
    setApplying(true);
    try {
      const res = await adminApi.applyTradesToStaging(selectedTradeIds);
      toast.success(res.message);
      setTradesOpen(false);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Apply failed");
    } finally {
      setApplying(false);
    }
  }

  function toggleTrade(id: number, checked: boolean) {
    setSelectedTradeIds((prev) =>
      checked ? [...prev, id] : prev.filter((x) => x !== id)
    );
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Staging Dock</h1>
          <p className="text-muted-foreground">
            Review cards before they go live in inventory and POS
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link href="/admin/intake">
            <Button variant="outline">+ Intake</Button>
          </Link>
          <Button variant="outline" onClick={openApplyTrades} disabled={!items.length}>
            Apply trade values
          </Button>
          <Button onClick={commitAll} disabled={!items.length}>
            Commit All to Inventory
          </Button>
        </div>
      </div>

      {loading ? (
        <p className="text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <div className="rounded-lg border border-dashed py-16 text-center">
          <p className="text-muted-foreground">Staging dock is empty</p>
          <Link href="/admin/intake" className="mt-2 inline-block text-primary">
            Add cards via Intake →
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((item) => (
            <div
              key={item.id}
              className="flex items-center gap-4 rounded-lg border p-4"
            >
              {item.image_url ? (
                <div className="relative h-[70px] w-[50px] shrink-0 overflow-hidden rounded border">
                  <Image
                    src={item.image_url}
                    alt={item.name}
                    fill
                    className="object-cover"
                    unoptimized
                  />
                </div>
              ) : (
                <div className="flex h-[70px] w-[50px] items-center justify-center rounded border bg-muted text-xs text-muted-foreground">
                  No img
                </div>
              )}
              <div className="min-w-0 flex-1">
                <p className="font-medium">{item.name}</p>
                <p className="text-sm text-muted-foreground">
                  {item.sku} · {item.set_name ?? "—"} · #{item.sequence_number ?? "—"}
                </p>
                <p className="text-sm">
                  Mkt ${item.market_price.toFixed(2)} · Sell $
                  {item.suggested_price.toFixed(2)} · Qty {item.quantity}
                </p>
              </div>
              <div className="flex shrink-0 flex-wrap gap-2">
                <Button size="sm" variant="outline" onClick={() => refetchOne(item)}>
                  Re-fetch
                </Button>
                <Button size="sm" variant="outline" onClick={() => deleteOne(item.id)}>
                  Delete
                </Button>
                <Button size="sm" onClick={() => commitOne(item.id)}>
                  Commit
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      {tradesOpen && (
        <div className="mb-6 rounded-lg border bg-muted/30 p-4">
          <h2 className="text-lg font-semibold">Apply trade values to staging</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Distributes cash paid from selected POS trades across all staging items
            by market weight, then promotes them to inventory.
          </p>
          <div className="my-4 space-y-3">
            {trades.map((trade) => (
              <label
                key={trade.id}
                className="flex cursor-pointer items-center gap-3 rounded-md border bg-background p-3"
              >
                <Checkbox
                  checked={selectedTradeIds.includes(trade.id)}
                  onCheckedChange={(v) => toggleTrade(trade.id, v === true)}
                />
                <div>
                  <p className="font-medium">Trade #{trade.id}</p>
                  <p className="text-sm text-muted-foreground">
                    Market ${trade.total_market_value.toFixed(2)} · Cash paid $
                    {trade.total_cash_paid.toFixed(2)}
                  </p>
                </div>
              </label>
            ))}
          </div>
          <div className="flex gap-2">
            <Button onClick={applyTrades} disabled={applying}>
              {applying ? "Applying…" : "Apply & promote to inventory"}
            </Button>
            <Button variant="outline" onClick={() => setTradesOpen(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
