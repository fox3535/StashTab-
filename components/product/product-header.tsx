"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ScanBarcode } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";

const titles: Record<string, string> = {
  "/pos": "Sell",
  "/pos/find": "Find",
  "/pos/pulls": "Pulls",
  "/pos/stats": "Stats",
  "/pos/more": "More",
  "/admin": "Overview",
  "/admin/dashboard": "Dashboard",
  "/admin/intake": "Intake",
  "/admin/staging": "Staging Dock",
  "/admin/inventory": "Inventory",
  "/admin/import": "CSV Import",
  "/admin/shopify/sync": "Shopify Sync",
  "/admin/shopify/review": "Shopify Review",
  "/admin/settings": "Settings",
  "/admin/reconciliation": "Reconciliation",
  "/admin/reports": "Reports",
  "/admin/paperweight": "Paperweight",
  "/admin/resticker": "Resticker",
};

function getTitle(pathname: string): string {
  if (titles[pathname]) return titles[pathname];
  const match = Object.entries(titles)
    .filter(([path]) => path !== "/admin" && path !== "/pos")
    .find(([path]) => pathname.startsWith(path));
  return match?.[1] ?? "StashTab";
}

export function ProductHeader() {
  const pathname = usePathname();
  const router = useRouter();
  const [q, setQ] = useState("");

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    const query = q.trim();
    router.push(query ? `/pos/find?q=${encodeURIComponent(query)}` : "/pos/find");
    setQ("");
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 border-b border-border bg-gunmetal px-4 lg:px-6">
      <SidebarTrigger className="-ml-1 hover:text-neon" />
      <Separator orientation="vertical" className="mr-1 h-4 bg-border" />
      <h1 className="font-display text-base font-semibold tracking-tight text-foreground">
        {getTitle(pathname)}
      </h1>

      {/* Global barcode / SKU lookup */}
      <form
        onSubmit={submitSearch}
        className="group ml-auto flex w-full max-w-xs items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 transition-all duration-200 focus-within:border-neon focus-within:shadow-[0_0_14px_rgba(139,92,246,0.25)] sm:max-w-sm"
      >
        <ScanBarcode className="size-4 shrink-0 text-steel transition-colors duration-200 group-focus-within:text-neon" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Scan barcode or search SKU..."
          autoComplete="off"
          className="w-full bg-transparent font-mono text-xs text-foreground outline-none placeholder:text-steel/60"
          aria-label="Scan barcode or search SKU"
        />
        <kbd className="hidden shrink-0 rounded border border-border bg-gunmetal px-1.5 py-0.5 font-mono text-[9px] text-steel sm:block">
          ⏎
        </kbd>
      </form>
    </header>
  );
}
