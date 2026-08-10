import Link from "next/link";

const adminLinks = [
  { href: "/admin/dashboard", label: "Dashboard", desc: "KPIs and overview" },
  { href: "/admin/intake", label: "Intake", desc: "Manual card intake" },
  { href: "/admin/staging", label: "Staging", desc: "Staging dock" },
  { href: "/admin/inventory", label: "Inventory", desc: "Full vault" },
  { href: "/admin/import", label: "CSV Import", desc: "Bulk import" },
  { href: "/admin/shopify/review", label: "Shopify Review", desc: "Review & sync" },
  { href: "/admin/shopify/sync", label: "Shopify Sync", desc: "Sync status" },
  { href: "/admin/settings", label: "Settings", desc: "Buy/trade rates" },
  { href: "/admin/reconciliation", label: "Reconciliation", desc: "Collectr CSV" },
  { href: "/admin/reports", label: "Reports", desc: "Trade history" },
];

export default function AdminHome() {
  return (
    <div className="p-6">
      <header className="mb-6">
        <h1 className="text-2xl font-bold">StashTab Admin</h1>
        <p className="text-muted-foreground">
          Desktop inventory management
        </p>
        <Link href="/pos" className="mt-2 inline-block text-sm text-primary">
          ← Back to POS
        </Link>
      </header>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {adminLinks.map((link) => (
          <Link
            key={link.href}
            href={link.href}
            className="rounded-lg border p-4 transition-colors hover:bg-muted/50"
          >
            <p className="font-medium">{link.label}</p>
            <p className="text-sm text-muted-foreground">{link.desc}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
