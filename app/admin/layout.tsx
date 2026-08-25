import { ProductShell } from "@/components/product/product-shell";
import { AdminBillingGate } from "@/components/admin-billing-gate";
import { AdminApiAuthGate } from "@/components/admin-api-auth-gate";
import { Toaster } from "@/components/ui/sonner";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ProductShell>
        <AdminBillingGate>
          <AdminApiAuthGate>{children}</AdminApiAuthGate>
        </AdminBillingGate>
      </ProductShell>
      <Toaster position="top-center" richColors />
    </>
  );
}
