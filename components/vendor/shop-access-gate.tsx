"use client";

import { SignOutButton } from "@/components/vendor/sign-out-button";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { LockedRouteGate } from "@/components/vendor/locked-route-gate";
import { VendorStatePanel } from "@/components/vendor/vendor-patterns";

export function ShopAccessGate({ children }: { children: React.ReactNode }) {
  const { shops, selectedShop, phase, message, selectShop } = useVendorShop();

  if (phase === "loading") {
    return (
      <div className="p-6" role="status" aria-live="polite">
        <p className="font-mono text-sm text-steel">Loading shop access…</p>
        <div className="mt-4 h-24 animate-pulse rounded-md bg-gunmetal motion-reduce:animate-none" />
      </div>
    );
  }

  if (phase === "session") {
    return (
      <VendorStatePanel role="alert" title="Session expired" detail={message || "Session expired. Sign in again."}>
        <div className="mt-4">
          <SignOutButton />
        </div>
      </VendorStatePanel>
    );
  }

  if (phase === "empty") {
    return (
      <VendorStatePanel
        title="No shop access"
        detail="Your account is signed in, but it is not a member of any shop."
      >
        <div className="mt-4">
          <SignOutButton />
        </div>
      </VendorStatePanel>
    );
  }

  if (phase === "error") {
    return (
      <VendorStatePanel role="alert" title="Shop access unavailable" detail={message}>
        <div className="mt-4">
          <SignOutButton />
        </div>
      </VendorStatePanel>
    );
  }

  if (phase === "choose") {
    return (
      <VendorStatePanel title="Choose a shop" className="max-w-lg">
        <p className="mt-2 text-sm text-steel" id="shop-select-help">
          {message || "Select a shop you are authorized to use."}
        </p>
        <label className="mt-4 block font-mono text-xs uppercase tracking-[0.16em] text-steel" htmlFor="shop-select">
          Authorized shops
        </label>
        <select
          id="shop-select"
          className="mt-2 w-full rounded-md border border-border bg-surface px-3 py-2 text-sm text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon"
          defaultValue=""
          aria-describedby="shop-select-help"
          onChange={(event) => {
            if (event.target.value) selectShop(event.target.value);
          }}
        >
          <option value="" disabled>
            Select…
          </option>
          {shops.map((shop) => (
            <option key={shop.id} value={shop.id}>
              {shop.name} ({shop.role})
            </option>
          ))}
        </select>
        <div className="mt-4">
          <SignOutButton />
        </div>
      </VendorStatePanel>
    );
  }

  if (!selectedShop) {
    return (
      <p className="p-6 font-mono text-sm text-steel" role="status">
        Choose a shop to continue.
      </p>
    );
  }

  return <LockedRouteGate>{children}</LockedRouteGate>;
}
