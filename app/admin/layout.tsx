import { ProductShell } from "@/components/product/product-shell";
import { AdminBillingGate } from "@/components/admin-billing-gate";
import { Toaster } from "@/components/ui/sonner";

export default function AdminLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <ProductShell>
        <AdminBillingGate>{children}</AdminBillingGate>
      </ProductShell>
      <Toaster position="top-center" richColors />
    </>
  );
}
