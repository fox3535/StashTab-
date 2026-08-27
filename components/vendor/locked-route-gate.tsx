"use client";

import { usePathname } from "next/navigation";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";

const LOCKED_EXACT = new Set(["/pos"]);
const LOCKED_PREFIXES = [
  "/admin/intake",
  "/admin/staging",
  "/admin/resticker",
  "/admin/import",
  "/admin/shopify",
  "/admin/settings",
  "/admin/reconciliation",
  "/admin/paperweight",
  "/admin/reports",
  "/admin/dashboard",
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
