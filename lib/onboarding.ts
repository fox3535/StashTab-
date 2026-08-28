// Pure vendor onboarding state helpers (F1 vendor-core batch).
//
// Read-only state math for the accepted FastAPI shop contracts:
// GET /shops/me/memberships (Clerk bearer only) and POST /shops
// (name + slug only). Never send caller identity headers, never fall back
// to a dev shop id, and never collect Shopify credentials here.

import type { VendorErrorKind } from "@/lib/vendor-api-error";

export const MAX_SHOP_NAME_LENGTH = 80;
export const MAX_SHOP_SLUG_LENGTH = 80;

/** Lowercase ASCII slug: runs of non-alphanumerics become a single dash. */
export function normalizeShopSlug(raw: string): string {
  return raw
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

/** Slug auto-suggestion follows the name until the slug field is edited. */
export function suggestSlug(name: string, slugEdited: boolean, currentSlug: string): string {
  return slugEdited ? currentSlug : normalizeShopSlug(name);
}

export function validateShopSetup(name: string, slug: string): string | null {
  const trimmedName = name.trim();
  if (!trimmedName) return "Shop name is required.";
  if (trimmedName.length > MAX_SHOP_NAME_LENGTH) {
    return `Shop name must be ${MAX_SHOP_NAME_LENGTH} characters or fewer.`;
  }
  const normalizedSlug = normalizeShopSlug(slug);
  if (!normalizedSlug) return "URL slug is required.";
  if (normalizedSlug.length > MAX_SHOP_SLUG_LENGTH) {
    return `URL slug must be ${MAX_SHOP_SLUG_LENGTH} characters or fewer.`;
  }
  return null;
}

export type OnboardingScreen = "session" | "loading" | "enter" | "form" | "error";

/**
 * Membership-driven routing: signed-out/expired sessions see the session
 * panel; one or more memberships go straight to the dashboard; zero
 * memberships get the vendor-shop setup form.
 */
export function decideOnboardingScreen(args: {
  clerkLoaded: boolean;
  isSignedIn: boolean;
  membershipsLoading: boolean;
  membershipsError: string;
  membershipCount: number;
}): OnboardingScreen {
  if (!args.clerkLoaded) return "loading";
  if (!args.isSignedIn) return "session";
  if (args.membershipsLoading) return "loading";
  if (args.membershipsError) return "error";
  if (args.membershipCount > 0) return "enter";
  return "form";
}

/** Duplicate-slug conflicts get a fixable message; everything else is classified upstream. */
export function messageForCreateFailure(kind: VendorErrorKind, message: string): string {
  if (kind === "conflict") {
    return "That URL slug is already taken. Choose a different slug and try again.";
  }
  return message;
}
