"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { mimirApi } from "@/lib/mimir-api";

const SHOP_ID = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";

export default function ShopifySyncPage() {
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);
  const [pulling, setPulling] = useState(false);
  const apiOpts = { shopId: SHOP_ID };

  async function loadStatus() {
    if (!SHOP_ID) return;
    try {
      const data = await mimirApi.syncStatus(apiOpts);
      setPending(data.pending_count);
    } catch {
      // ignore
    }
  }

  async function syncNow() {
    if (!SHOP_ID) return;
    setSyncing(true);
    try {
      await mimirApi.syncNow(apiOpts);
      toast.success("Full sync started (pull orders + outbox)");
      setTimeout(loadStatus, 2000);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }

  async function pullOrders() {
    if (!SHOP_ID) return;
    setPulling(true);
    try {
      const res = await mimirApi.pullOrders(apiOpts);
      toast.success(res.message || `Pulled ${res.new_pulls} items`);
      await loadStatus();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Pull failed");
    } finally {
      setPulling(false);
    }
  }

  async function verifyShopify() {
    setSyncing(true);
    try {
      const res = await mimirApi.verifyShopify({ shopId: SHOP_ID });
      toast.success(res.message);
      await loadStatus();
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Verify failed");
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, []);

  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold">Shopify Sync</h1>
      <p className="mt-2 text-muted-foreground">
        Pending outbox items: <strong>{pending}</strong>
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        <Button onClick={syncNow} disabled={syncing}>
          {syncing ? "Syncing…" : "Full sync now"}
        </Button>
        <Button variant="outline" onClick={pullOrders} disabled={pulling}>
          {pulling ? "Pulling…" : "Pull online orders"}
        </Button>
        <Button variant="outline" onClick={verifyShopify} disabled={syncing}>
          Verify catalog
        </Button>
        <Button variant="ghost" onClick={loadStatus}>
          Refresh status
        </Button>
      </div>
      <p className="mt-4 max-w-lg text-sm text-muted-foreground">
        Configure Shopify credentials in Settings first. Pull orders fills the POS
        Pulls tab and triggers online sale toasts on the show floor.
      </p>
    </div>
  );
}
