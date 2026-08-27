"use client";

import { useClerk } from "@clerk/nextjs";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";

export function SignOutButton({ compact = false }: { compact?: boolean }) {
  const { signOut } = useClerk();
  const { clearLocalSession } = useVendorShop();

  async function onSignOut() {
    clearLocalSession();
    await signOut({ redirectUrl: "/" });
  }

  return (
    <button
      type="button"
      onClick={onSignOut}
      className="min-h-11 min-w-11 rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs uppercase tracking-[0.14em] text-foreground transition-colors hover:border-neon/50 hover:text-neon focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon"
    >
      {compact ? "Sign out" : "Sign out"}
    </button>
  );
}
