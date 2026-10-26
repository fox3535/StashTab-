"use client";

import { usePathname } from "next/navigation";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";

const LOCKED_EXACT = new Set(["/pos"]);
const LOCKED_PREFIXES = [
  "/admin/intake",
  "/admin/import",
  // Bare /admin/shopify renders its own honest FeatureNotReady page;
  // only the functional subroutes stay gate-locked.
  "/admin/shopify/sync",
  "/admin/shopify/review",
  "/admin/settings",
  // /admin/reconciliation ships the read-only Inventory Integrity screen
  // (slice-11) and /admin/reports ships the read-only Recent Trade
  // History screen (slice-09); both stay out of the lock list.
  // /admin/paperweight ships the read-only Paperweight Report (slice-12)
  // and /admin/resticker the read-only Resticker Queue (slice-13).
  // /admin/staging ships the read-only Staging Queue (slice-15); staging
  // commit (the inventory receive path) stays unwired.
  "/pos/pulls",
  "/pos/stats",
];

function isLockedPath(pathname: string): boolean {
  if (LOCKED_EXACT.has(pathname)) return true;
  return LOCKED_PREFIXES.some((prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`));
}

export function LockedRouteGate({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  if (isLockedPath(pathname)) {
    return (
      <FeatureNotReady
        title="This feature is not ready"
        detail="This screen is deferred. It will not sell, sync, commit intake, or write inventory."
      />
    );
  }
  return <>{children}</>;
}
