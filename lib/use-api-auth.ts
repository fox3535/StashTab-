"use client";

import { useCallback } from "react";
import { useAuth } from "@clerk/nextjs";
import {
  SessionExpiredError,
  type ProtectedApiAuth,
} from "@/lib/protected-api-headers";

const SHOP_HINT = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";

export function useApiAuth() {
  const { getToken, isLoaded, isSignedIn } = useAuth();

  const getAuth = useCallback(async (): Promise<ProtectedApiAuth> => {
    const token = await getToken();
    if (!token) {
      throw new SessionExpiredError();
    }
    return { authToken: token, shopId: SHOP_HINT || undefined };
  }, [getToken]);

  return { getAuth, shopHint: SHOP_HINT, isLoaded, isSignedIn };
}
