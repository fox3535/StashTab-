"use client";

import { useEffect, useState } from "react";
import { mimirApi } from "@/lib/mimir-api";
import { usePos } from "../pos-context";
import { Button } from "@/components/ui/button";
import { RefreshCw } from "lucide-react";

export function SyncStatusBar() {
  const { apiOpts, shopId } = usePos();
  const [pending, setPending] = useState(0);
  const [syncing, setSyncing] = useState(false);

  async function loadStatus() {
    if (!shopId) return;
    try {
      const status = await mimirApi.syncStatus(apiOpts);
      setPending(status.pending_count);
    } catch {
      /* ignore when API offline */
    }
  }

  async function handleSyncNow() {
    setSyncing(true);
    try {
      await mimirApi.syncNow(apiOpts);
      setTimeout(loadStatus, 2000);
    } finally {
      setSyncing(false);
    }
  }

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 15000);
    return () => clearInterval(interval);
  }, [shopId]);

  if (!shopId) return null;

  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-border bg-gunmetal px-3 py-2 font-mono text-xs text-steel">
      <span>
        Shopify sync:{" "}
        <span className={pending > 0 ? "text-holo-gold" : "text-emerald-400"}>
          {pending > 0 ? `${pending} pending` : "Up to date"}
        </span>
      </span>
      <Button
        variant="ghost"
        size="sm"
        className="h-8 min-h-8 px-2 text-steel transition-colors duration-200 hover:bg-neon/10 hover:text-neon"
        onClick={handleSyncNow}
        disabled={syncing}
      >
        <RefreshCw className={`mr-1 h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} />
        Sync Now
      </Button>
    </div>
  );
}
