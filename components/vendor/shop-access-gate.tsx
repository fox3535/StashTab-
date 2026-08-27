"use client";

import { SignOutButton } from "@/components/vendor/sign-out-button";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { LockedRouteGate } from "@/components/vendor/locked-route-gate";

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
      <section className="m-4 rounded-lg border border-border bg-gunmetal p-6" role="alert">
        <h2 className="font-display text-lg font-semibold">Session expired</h2>
        <p className="mt-2 text-sm text-steel">{message || "Session expired. Sign in again."}</p>
        <div className="mt-4">
          <SignOutButton />
        </div>
      </section>
    );
  }

  if (phase === "empty") {
    return (
      <section className="m-4 rounded-lg border border-border bg-gunmetal p-6" role="status">
        <h2 className="font-display text-lg font-semibold">No shop access</h2>
        <p className="mt-2 text-sm text-steel">
          Your account is signed in, but it is not a member of any shop.
        </p>
        <div className="mt-4">
          <SignOutButton />
        </div>
      </section>
    );
  }

  if (phase === "error") {
    return (
      <section className="m-4 rounded-lg border border-border bg-gunmetal p-6" role="alert">
        <h2 className="font-display text-lg font-semibold">Shop access unavailable</h2>
        <p className="mt-2 text-sm text-steel">{message}</p>
        <div className="mt-4">
          <SignOutButton />
        </div>
      </section>
    );
  }

  if (phase === "choose") {
    return (
      <section className="m-4 max-w-lg rounded-lg border border-border bg-gunmetal p-6">
        <h2 className="font-display text-lg font-semibold">Choose a shop</h2>
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
      </section>
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
