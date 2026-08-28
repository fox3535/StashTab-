"use client";

import { FeatureNotReady } from "@/components/vendor/feature-not-ready";

export default function ShopifyHubPage() {
  return (
    <FeatureNotReady
      title="Shopify is not ready"
      detail="Shopify connection and sync are deferred. Nothing here can sync, list, or write inventory. Use Shopify Sync or Shopify Review entries only after their slice is accepted."
    />
  );
}
