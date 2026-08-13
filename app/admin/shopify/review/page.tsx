"use client";

import { useCallback, useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";

const API = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8001";
const SHOP_ID = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";

type UpdatedItem = {
  id: number;
  sku: string;
  name: string;
  old_price: number | null;
  price: number;
  shop_listing_price: number | null;
};

export default function ShopifyReviewPage() {
  const [items, setItems] = useState<UpdatedItem[]>([]);
  const [loading, setLoading] = useState(false);

  const load = useCallback(async () => {
    if (!SHOP_ID) return;
    const res = await fetch(`${API}/api/v1/admin/inventory/updated`, {
      headers: { "X-Shop-Id": SHOP_ID },
    });
    if (res.ok) {
      const data = await res.json();
      setItems(data.items ?? []);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  async function approveOne(id: number) {
    setLoading(true);
    try {
      const res = await fetch(
        `${API}/api/v1/admin/inventory/${id}/approve-update`,
        { method: "POST", headers: { "X-Shop-Id": SHOP_ID } }
      );
      if (!res.ok) throw new Error(await res.text());
      toast.success("Queued for Shopify sync");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Approve failed");
    } finally {
      setLoading(false);
    }
  }

  async function rejectOne(id: number) {
    setLoading(true);
    try {
      const res = await fetch(
        `${API}/api/v1/admin/inventory/${id}/reject-update`,
        { method: "POST", headers: { "X-Shop-Id": SHOP_ID } }
      );
      if (!res.ok) throw new Error(await res.text());
      toast.success("Reverted price update");
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Reject failed");
    } finally {
      setLoading(false);
    }
  }

  async function approveUnder5() {
    setLoading(true);
    try {
      const res = await fetch(`${API}/api/v1/admin/inventory/approve-under-5`, {
        method: "POST",
        headers: { "X-Shop-Id": SHOP_ID },
      });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      toast.success(`Approved ${data.approved} updates under $5`);
      await load();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Bulk approve failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">Shopify Review</h1>
          <p className="mt-2 text-muted-foreground">
            Approve Collectr price updates before pushing to Shopify.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" onClick={load} disabled={loading}>
            Refresh
          </Button>
          <Button onClick={approveUnder5} disabled={loading || !items.length}>
            Approve all under $5
          </Button>
        </div>
      </div>

      <ul className="mt-6 space-y-2">
        {!items.length && (
          <li className="text-muted-foreground">No pending price updates.</li>
        )}
        {items.map((item) => (
          <li
            key={item.id}
            className="flex flex-wrap items-center justify-between gap-2 rounded-lg border p-3"
          >
            <div>
              <p className="font-medium">{item.name}</p>
              <p className="text-sm text-muted-foreground">
                {item.sku} · ${item.old_price?.toFixed(2) ?? "?"} → $
                {item.price.toFixed(2)} (shop ${item.shop_listing_price?.toFixed(2) ?? "?"})
              </p>
            </div>
            <div className="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={loading}
                onClick={() => rejectOne(item.id)}
              >
                Reject
              </Button>
              <Button
                size="sm"
                disabled={loading}
                onClick={() => approveOne(item.id)}
              >
                Approve & sync
              </Button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
