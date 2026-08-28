"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, useClerk, useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { mimirApi } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { parseMembershipsPayload, clearShopPreference, writeShopPreference } from "@/lib/shop-session";
import { VendorStatePanel } from "@/components/vendor/vendor-patterns";
import {
  decideOnboardingScreen,
  messageForCreateFailure,
  normalizeShopSlug,
  suggestSlug,
  validateShopSetup,
} from "@/lib/onboarding";

function OnboardingSignOut() {
  const { signOut } = useClerk();

  async function onSignOut() {
    clearShopPreference();
    await signOut({ redirectUrl: "/" });
  }

  return (
    <button
      type="button"
      onClick={onSignOut}
      className="min-h-11 min-w-11 rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs uppercase tracking-[0.14em] text-foreground transition-colors hover:border-neon/50 hover:text-neon focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon"
    >
      Sign out
    </button>
  );
}

export default function OnboardingPage() {
  const { user, isLoaded: userLoaded } = useUser();
  const { getToken, isLoaded: authLoaded, isSignedIn } = useAuth();
  const router = useRouter();

  const [membershipCount, setMembershipCount] = useState(0);
  const [membershipsLoading, setMembershipsLoading] = useState(true);
  const [membershipsError, setMembershipsError] = useState("");

  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);
  const [validationError, setValidationError] = useState("");
  const [createError, setCreateError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const inFlightRef = useRef(false);

  const loadMemberships = useCallback(async () => {
    setMembershipsLoading(true);
    setMembershipsError("");
    try {
      const token = await getToken();
      if (!token) {
        setMembershipsError("Session expired. Sign in again.");
        return;
      }
      const payload = await mimirApi.listMyMemberships({ authToken: token });
      const shops = parseMembershipsPayload(payload);
      setMembershipCount(shops.length);
      if (shops.length > 0) router.replace("/admin/dashboard");
    } catch (err) {
      setMembershipCount(0);
      setMembershipsError(classifyVendorError(err).message);
    } finally {
      setMembershipsLoading(false);
    }
  }, [getToken, router]);

  useEffect(() => {
    if (!authLoaded || !userLoaded || !isSignedIn) return;
    void loadMemberships();
  }, [authLoaded, userLoaded, isSignedIn, loadMemberships]);

  async function createShop() {
    // Double submission guard: state plus ref survive quick re-renders.
    if (inFlightRef.current || submitting) return;
    // The displayed value is the suggestion; submit what the vendor sees.
    const effectiveSlug = suggestSlug(name, slugEdited, slug);
    const invalid = validateShopSetup(name, effectiveSlug);
    if (invalid) {
      setValidationError(invalid);
      return;
    }
    setValidationError("");
    setCreateError("");
    inFlightRef.current = true;
    setSubmitting(true);
    try {
      const token = await getToken();
      if (!token) {
        setCreateError("Session expired. Sign in again.");
        return;
      }
      const normalizedSlug = normalizeShopSlug(effectiveSlug);
      // POST /shops derives identity from the Clerk bearer token only.
      const shop = await mimirApi.createShop(name.trim(), normalizedSlug, { authToken: token });
      // Refresh memberships, then store only the validated preference.
      try {
        const payload = await mimirApi.listMyMemberships({ authToken: token });
        parseMembershipsPayload(payload);
      } catch {
        /* the dashboard shell re-verifies memberships on entry */
      }
      writeShopPreference(shop.id);
      router.replace("/admin/dashboard");
    } catch (err) {
      const classified = classifyVendorError(err);
      setCreateError(messageForCreateFailure(classified.kind, classified.message));
    } finally {
      inFlightRef.current = false;
      setSubmitting(false);
    }
  }

  const screen = decideOnboardingScreen({
    clerkLoaded: authLoaded && userLoaded,
    isSignedIn: Boolean(isSignedIn && user),
    membershipsLoading,
    membershipsError,
    membershipCount,
  });

  return (
    <div className="mx-auto flex min-h-screen w-full max-w-md items-center overflow-x-hidden p-4 md:p-6">
      <div className="w-full rounded-lg border border-border bg-gunmetal p-6">
        <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Welcome to StashTab
        </h1>
        <p className="mt-1 text-sm text-steel">Vendor shop setup</p>

        {screen === "loading" ? (
          <div className="mt-6" role="status" aria-live="polite">
            <div className="h-24 animate-pulse rounded-md bg-surface motion-reduce:animate-none" />
            <p className="mt-3 font-mono text-sm text-steel">Checking your shop access…</p>
          </div>
        ) : null}

        {screen === "session" ? (
          <VendorStatePanel
            role="alert"
            className="m-0 mt-6"
            title="Session expired"
            detail="Session expired. Sign in again."
          >
            <div className="mt-4">
              <OnboardingSignOut />
            </div>
          </VendorStatePanel>
        ) : null}

        {screen === "enter" ? (
          <p className="mt-6 font-mono text-sm text-steel" role="status">
            Opening your dashboard…
          </p>
        ) : null}

        {screen === "error" ? (
          <VendorStatePanel
            role="alert"
            className="m-0 mt-6"
            title="Shop access unavailable"
            detail={membershipsError}
          >
            <div className="mt-4 flex flex-wrap gap-2">
              <Button
                type="button"
                variant="outline"
                className="min-h-11 border-border font-mono text-sm"
                onClick={() => void loadMemberships()}
              >
                Retry
              </Button>
              <OnboardingSignOut />
            </div>
          </VendorStatePanel>
        ) : null}

        {screen === "form" ? (
          <form
            className="mt-6 space-y-4"
            noValidate
            onSubmit={(event) => {
              event.preventDefault();
              void createShop();
            }}
          >
            <p className="text-sm text-steel">
              Your account is signed in but is not a member of any shop yet. Create your vendor
              shop to get started.
            </p>
            <div>
              <Label htmlFor="shop-name" className="font-mono text-xs uppercase tracking-[0.16em] text-steel">
                Shop name
              </Label>
              <Input
                id="shop-name"
                className="mt-2 min-h-11 border-border bg-surface font-mono text-sm focus-visible:border-neon"
                value={name}
                onChange={(event) => setName(event.target.value)}
                placeholder="My Card Shop"
                autoComplete="organization"
                aria-describedby="shop-setup-help"
                required
              />
            </div>
            <div>
              <Label htmlFor="shop-slug" className="font-mono text-xs uppercase tracking-[0.16em] text-steel">
                URL slug
              </Label>
              <Input
                id="shop-slug"
                className="mt-2 min-h-11 border-border bg-surface font-mono text-sm focus-visible:border-neon"
                value={suggestSlug(name, slugEdited, slug)}
                onChange={(event) => {
                  setSlugEdited(true);
                  setSlug(event.target.value);
                }}
                placeholder="my-card-shop"
                aria-describedby="shop-setup-help"
                required
              />
            </div>
            <p id="shop-setup-help" className="text-xs text-steel/80">
              Shopify sync, payments, and notifications are deferred — nothing else is collected
              here. If the slug is already taken you will be told and can pick another.
            </p>
            <div aria-live="polite" className="sr-only">
              {submitting ? "Creating your shop" : ""}
            </div>
            {validationError || createError ? (
              <p className="rounded-md border border-border bg-surface p-3 text-sm text-steel" role="alert">
                {validationError || createError}
              </p>
            ) : null}
            <Button
              type="submit"
              className="min-h-11 w-full bg-neon font-display font-bold text-white hover:bg-neon/90"
              disabled={submitting}
            >
              {submitting ? "Creating…" : "Create shop"}
            </Button>
            <p className="text-xs text-steel/70">
              Only your Clerk session is used for identity. No user-ID headers, no dev shop
              fallback, no Shopify credentials.
            </p>
          </form>
        ) : null}
      </div>
    </div>
  );
}
