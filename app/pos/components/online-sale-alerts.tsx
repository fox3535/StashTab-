"use client";

import { useEffect, useRef } from "react";
import { toast } from "sonner";
import { mimirApi } from "@/lib/mimir-api";
import { usePos } from "../pos-context";

export function OnlineSaleAlerts() {
  const { apiOpts, shopId } = usePos();
  const seenRef = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!shopId) return;

    let cancelled = false;

    async function poll() {
      try {
        const { notifications } = await mimirApi.syncNotifications(apiOpts);
        if (cancelled) return;
        for (const note of notifications) {
          if (seenRef.current.has(note.id)) continue;
          seenRef.current.add(note.id);
          toast.info(`Online sale: ${note.card_name}`, {
            description: note.order_id ? `Order #${note.order_id}` : note.sku,
            duration: 8000,
          });
        }
      } catch {
        // Ignore polling errors — API may be offline during dev
      }
    }

    poll();
    const interval = setInterval(poll, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [apiOpts, shopId]);

  return null;
}
