import type { Metadata, Viewport } from "next";
import { Toaster } from "@/components/ui/sonner";
import { ProductShell } from "@/components/product/product-shell";
import { OnlineSaleAlerts } from "./components/online-sale-alerts";
import { PosProvider } from "./pos-context";
import { VendorShopProvider } from "@/components/vendor/vendor-shop-provider";
import { ShopAccessGate } from "@/components/vendor/shop-access-gate";

export const metadata: Metadata = {
  title: "StashTab POS",
  description: "Mobile show-floor point of sale",
  manifest: "/manifest.json",
  appleWebApp: {
    capable: true,
    statusBarStyle: "black-translucent",
    title: "StashTab",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
  themeColor: "#000000",
};

export default function PosLayout({ children }: { children: React.ReactNode }) {
  return (
    <VendorShopProvider>
      <ShopAccessGate>
        <PosProvider>
          <ProductShell variant="full">
            <div className="flex min-h-[calc(100svh-var(--header-height))] w-full flex-1 flex-col bg-obsidian text-foreground">
              <OnlineSaleAlerts />
              {children}
            </div>
          </ProductShell>
        </PosProvider>
      </ShopAccessGate>
      <Toaster position="top-center" richColors />
    </VendorShopProvider>
  );
}
