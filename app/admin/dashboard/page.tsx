"use client";

import Link from "next/link";
import { ArrowLeftRight, Package, Receipt, Search } from "lucide-react";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { PageHeader } from "@/components/vendor/vendor-patterns";

type ReadyCard = {
  href: string;
  label: string;
  detail: string;
  icon: React.ComponentType<{ className?: string }>;
};

type DeferredCard = {
  label: string;
  detail: string;
};

const readyCards: ReadyCard[] = [
  {
    href: "/admin/inventory",
    label: "Inventory",
    detail: "Read-only search for in-stock cards. Edits, labels, and imports are not ready.",
    icon: Package,
  },
  {
    href: "/pos/find",
    label: "POS Find",
    detail: "Fast read-only booth lookup by SKU or barcode. Selling is not ready.",
    icon: Search,
  },
  {
    href: "/admin/sales",
    label: "Sales History",
    detail: "Read-only browse of recorded sales. Refunds, exports, and metrics are not ready.",
    icon: Receipt,
  },
  {
    href: "/admin/reports",
    label: "Recent Trades",
    detail: "Read-only view of up to the newest 200 trade transactions. Exports and metrics are not ready.",
    icon: ArrowLeftRight,
  },
];

const deferredCards: DeferredCard[] = [
  { label: "Intake", detail: "Card identification and intake commit are deferred." },
  { label: "POS checkout", detail: "Selling and checkout are deferred. No sale can be taken." },
  { label: "Shopify", detail: "Shopify connection and sync are deferred." },
  { label: "Notifications", detail: "Notification settings and push are deferred." },
  { label: "Payments", detail: "Payments are deferred. No billing is active." },
  { label: "Watch", detail: "Market Watch is advisory and deferred. No trading actions." },
];

export default function AdminDashboardPage() {
  const { selectedShop } = useVendorShop();

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <PageHeader
        className="mb-6"
        title="Dashboard"
        subtitle={`Vendor home for ${selectedShop?.name}. Live tools are read-only; deferred tools explain themselves. Metrics arrive with their own slices.`}
      />

      <section aria-label="Ready tools" className="mb-8">
        <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-steel/70">
          Ready
        </h2>
        <div className="grid gap-4 sm:grid-cols-2">
          {readyCards.map(({ href, label, detail, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className="group rounded-lg border border-border bg-gunmetal p-5 transition-colors hover:border-neon/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon"
            >
              <div className="flex items-center gap-2">
                <Icon className="size-4 text-neon" />
                <span className="font-display font-semibold text-foreground">{label}</span>
                <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-neon">
                  Read-only
                </span>
              </div>
              <p className="mt-2 text-sm text-steel">{detail}</p>
            </Link>
          ))}
        </div>
      </section>

      <section aria-label="Deferred tools" className="mb-4">
        <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-steel/70">
          Deferred
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {deferredCards.map(({ label, detail }) => (
            <li key={label} className="rounded-lg border border-border bg-gunmetal p-5">
              <div className="flex items-center gap-2">
                <span className="font-display font-semibold text-foreground">{label}</span>
                <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-steel/60">
                  Not ready
                </span>
              </div>
              <p className="mt-2 text-sm text-steel">{detail}</p>
            </li>
          ))}
        </ul>
      </section>

      <p className="text-xs text-steel/70">
        Revenue, inventory totals, alerts, and operational metrics are not shown
        until their data slices are accepted. This page never invents numbers.
      </p>
    </div>
  );
}
