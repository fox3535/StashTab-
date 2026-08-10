"use client";

import { useEffect, useState } from "react";
import { mimirApi } from "@/lib/mimir-api";
import { usePos } from "../pos-context";

type ApiStatus = "checking" | "ok" | "error";

export function ApiStatusBar() {
  const { shopId, apiOpts } = usePos();
  const [status, setStatus] = useState<ApiStatus>("checking");
  const [detail, setDetail] = useState("");

  useEffect(() => {
    let cancelled = false;

    async function check() {
      if (!shopId) {
        setStatus("error");
        setDetail("NEXT_PUBLIC_DEV_SHOP_ID not set — restart npm after editing .env.local");
        return;
      }

      setStatus("checking");
      try {
        await mimirApi.health();
        const inv = await mimirApi.searchInventory("", { ...apiOpts, limit: 1 });
        if (cancelled) return;
        setStatus("ok");
        setDetail(`API connected · ${inv.total} items in inventory`);
      } catch (e) {
        if (cancelled) return;
        setStatus("error");
        const msg = e instanceof Error ? e.message : "Cannot reach API";
        if (msg.includes("Failed to fetch") || msg.includes("NetworkError")) {
          setDetail(
            "API unreachable or CORS blocked — is Python API running on port 8001?"
          );
        } else {
          setDetail(msg.slice(0, 120));
        }
      }
    }

    check();
    return () => {
      cancelled = true;
    };
  }, [shopId, apiOpts]);

  if (status === "checking") {
    return (
      <div className="flex items-center gap-2 rounded-lg border border-border bg-gunmetal px-3 py-2 font-mono text-xs text-steel">
        <span className="size-1.5 animate-blink rounded-full bg-neon" />
        Connecting to API…
      </div>
    );
  }

  if (status === "error") {
    return (
      <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-3 py-2 font-mono text-xs text-red-300">
        {detail}
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2 rounded-lg border border-neon/25 bg-neon/5 px-3 py-2 font-mono text-xs text-neon">
      <span className="size-1.5 rounded-full bg-neon shadow-[0_0_8px_rgba(139,92,246,0.8)]" />
      {detail}
    </div>
  );
}
