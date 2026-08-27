"use client";

import { useAuth } from "@clerk/nextjs";

export function AdminApiAuthGate({ children }: { children: React.ReactNode }) {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) {
    return <p className="p-6 text-sm text-muted-foreground">Loading session…</p>;
  }
  if (!isSignedIn) {
    return (
      <p className="p-6 text-sm text-muted-foreground">
        Sign in required. Your session expired or you are not signed in.
      </p>
    );
  }
  return <>{children}</>;
}
