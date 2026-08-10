import { cn } from "@/lib/utils";
import { ProductHeader } from "@/components/product/product-header";
import { ProductSidebar } from "@/components/product/product-sidebar";
import { SidebarInset, SidebarProvider } from "@/components/ui/sidebar";

export function ProductShell({
  children,
  className,
  variant = "default",
}: {
  children: React.ReactNode;
  className?: string;
  /** default = padded admin-style; full = edge-to-edge content */
  variant?: "default" | "full";
}) {
  return (
    <SidebarProvider
      className="min-h-svh w-full overflow-x-hidden"
      style={
        {
          "--sidebar-width": "16rem",
          "--header-height": "3.5rem",
        } as React.CSSProperties
      }
    >
      <ProductSidebar />
      <SidebarInset className="flex min-h-svh w-full flex-col overflow-x-hidden bg-obsidian">
        <ProductHeader />
        <div
          className={cn(
            "flex w-full min-h-0 flex-1 flex-col",
            variant === "default" && "gap-4 p-6",
            className
          )}
        >
          {children}
        </div>
      </SidebarInset>
    </SidebarProvider>
  );
}
