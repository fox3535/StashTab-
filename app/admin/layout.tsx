import { ProductShell } from "@/components/product/product-shell";
import { AdminBillingGate } from "@/components/admin-billing-gate";
import { AdminApiAuthGate } from "@/components/admin-api-auth-gate";
import { Toaster } from "@/components/ui/sonner";
import { VendorShopProvider } from "@/components/vendor/vendor-shop-provider";
import { ShopAccessGate } from "@/components/vendor/shop-access-gate";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <VendorShopProvider>
        <ProductShell>
          <AdminBillingGate>
            <AdminApiAuthGate>
              <ShopAccessGate>{children}</ShopAccessGate>
            </AdminApiAuthGate>
          </AdminBillingGate>
        </ProductShell>
      </VendorShopProvider>
      <Toaster position="top-center" richColors />
    </>
  );
}
