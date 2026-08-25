"use client";

import { useEffect } from "react";
import { useAuth } from "@clerk/nextjs";
import { SessionExpiredError } from "@/lib/protected-api-headers";
import { setAdminAuthProvider } from "@/lib/admin-api";
import { setMimirAuthProvider } from "@/lib/mimir-api";

export function AdminApiAuthGate({ children }: { children: React.ReactNode }) {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  useEffect(() => {
    const provide = async () => {
      const token = await getToken();
      if (!token) throw new SessionExpiredError();
      return {
        authToken: token,
        shopId: process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "",
      };
    };
    setAdminAuthProvider(provide);
    setMimirAuthProvider(provide);
    return () => {
      setAdminAuthProvider(null);
      setMimirAuthProvider(null);
    };
  }, [getToken]);

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
