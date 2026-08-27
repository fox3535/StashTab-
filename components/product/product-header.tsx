"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { ScanBarcode } from "lucide-react";
import { Separator } from "@/components/ui/separator";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { SignOutButton } from "@/components/vendor/sign-out-button";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";

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
  const { shops, selectedShop, selectShop, phase } = useVendorShop();

  function submitSearch(e: React.FormEvent) {
    e.preventDefault();
    const query = q.trim();
    router.push(query ? `/pos/find?q=${encodeURIComponent(query)}` : "/pos/find");
    setQ("");
  }

  return (
    <header className="flex h-14 shrink-0 items-center gap-3 overflow-x-hidden border-b border-border bg-gunmetal px-4 lg:px-6">
      <SidebarTrigger className="-ml-1 hover:text-neon" />
      <Separator orientation="vertical" className="mr-1 h-4 bg-border" />
      <h1 className="font-display text-base font-semibold tracking-tight text-foreground">
        {getTitle(pathname)}
      </h1>

      <form
        onSubmit={submitSearch}
        className="group ml-auto flex min-w-0 w-full max-w-[10rem] items-center gap-2 rounded-md border border-border bg-surface px-3 py-1.5 transition-all duration-200 focus-within:border-neon focus-within:shadow-[0_0_14px_rgba(139,92,246,0.25)] sm:max-w-sm"
      >
        <ScanBarcode className="size-4 shrink-0 text-steel transition-colors duration-200 group-focus-within:text-neon" />
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search SKU..."
          autoComplete="off"
          className="w-full bg-transparent font-mono text-xs text-foreground outline-none placeholder:text-steel/60"
          aria-label="Search inventory SKU"
        />
      </form>

      {phase === "ready" && selectedShop && shops.length > 1 ? (
        <label className="hidden items-center gap-2 md:flex">
          <span className="sr-only">Shop</span>
          <select
            className="max-w-[9rem] rounded-md border border-border bg-surface px-2 py-1 font-mono text-xs text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon"
            value={selectedShop.id}
            onChange={(event) => selectShop(event.target.value)}
            aria-label="Authorized shop"
          >
            {shops.map((shop) => (
              <option key={shop.id} value={shop.id}>
                {shop.name}
              </option>
            ))}
          </select>
        </label>
      ) : selectedShop ? (
        <p className="hidden truncate font-mono text-xs text-steel md:block" title={selectedShop.name}>
          {selectedShop.name}
        </p>
      ) : null}

      <SignOutButton compact />
    </header>
  );
}
