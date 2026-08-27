"use client";

import Link from "next/link";
import { SignOutButton } from "@/components/vendor/sign-out-button";
import { FeatureNotReady } from "@/components/vendor/feature-not-ready";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { useState } from "react";

export default function MorePage() {
  const { selectedShop, shops, selectShop } = useVendorShop();
  const [locked, setLocked] = useState<string | null>(null);

  return (
    <div className="flex w-full max-w-full flex-col gap-4 overflow-x-hidden p-4 pt-[max(1rem,env(safe-area-inset-top))] md:p-6 lg:p-8">
      <header>
        <h1 className="font-display text-xl font-bold tracking-tight text-foreground">More</h1>
        <p className="text-sm text-steel">Account and shop. Selling and Shopify are not ready.</p>
      </header>

      {selectedShop ? (
        <p className="font-mono text-xs text-steel">Shop: {selectedShop.name}</p>
      ) : null}

      {shops.length > 1 ? (
        <label className="block text-sm">
          <span className="font-mono text-xs uppercase tracking-[0.16em] text-steel">Shop</span>
          <select
            className="mt-1 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm"
            value={selectedShop?.id ?? ""}
            onChange={(event) => selectShop(event.target.value)}
            aria-label="Authorized shop"
          >
            {shops.map((shop) => (
              <option key={shop.id} value={shop.id}>
                {shop.name} ({shop.role})
              </option>
            ))}
          </select>
        </label>
      ) : null}

      <div className="space-y-2">
        <Link
          href="/admin/inventory"
          className="block rounded-lg border border-border bg-gunmetal px-4 py-3 text-sm text-foreground hover:border-neon/40"
        >
          Inventory search →
        </Link>
        <button
          type="button"
          className="block w-full rounded-lg border border-border bg-gunmetal px-4 py-3 text-left text-sm text-steel"
          onClick={() => setLocked("Shopify")}
        >
          Shopify connection — not ready
        </button>
        <button
          type="button"
          className="block w-full rounded-lg border border-border bg-gunmetal px-4 py-3 text-left text-sm text-steel"
          onClick={() => setLocked("Notifications")}
        >
          Notification settings — not ready
        </button>
      </div>

      {locked ? (
        <FeatureNotReady
          title={`${locked} is not ready`}
          detail="This setting is deferred. It will not enable sync, push, or payments."
        />
      ) : null}

      <SignOutButton />
    </div>
  );
}
