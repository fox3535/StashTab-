"use client";

// Slice-14 adds three read-only stat tiles fed only by the accepted
// authenticated GET /api/v1/admin/dashboard contract, limited by owner
// decisions D1–D4 (docs/frontend-recovery-v1/PLAN-SLICE-14-DASHBOARD-
// METRICS.md) to in-stock SKUs, inventory value at sell price, and
// stagnant units. Sales money, staging, and Shopify sync figures are never
// read. A metrics failure shows "—" in the tiles and never hides the tool
// cards below.

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { ArrowLeftRight, BadgeDollarSign, Hourglass, Package, Receipt, Search, ShieldCheck, Sticker } from "lucide-react";
import { mimirApi, type DashboardMetrics } from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import { formatMetricCount, formatMetricMoney, isPositiveMetric } from "@/lib/dashboard-metrics";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import { PageHeader, VendorErrorBanner } from "@/components/vendor/vendor-patterns";

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
  {
    href: "/admin/price-updates",
    label: "Price Updates",
    detail: "Read-only review of inventory records with a pending/previous price update. Approving and repricing are not ready.",
    icon: BadgeDollarSign,
  },
  {
    href: "/admin/reconciliation",
    label: "Inventory Integrity",
    detail: "Read-only cutover status and reconciliation check. It compares snapshots with event-derived truth and never repairs anything.",
    icon: ShieldCheck,
  },
  {
    href: "/admin/paperweight",
    label: "Paperweight Report",
    detail: "Read-only list of in-stock items past the shop's paperweight cutoff (60 days by default), oldest first. Discounting and relisting are not ready.",
    icon: Hourglass,
  },
  {
    href: "/admin/resticker",
    label: "Resticker Queue",
    detail: "Read-only list of in-stock items whose printed sticker has drifted from the current price. Marking restickered and printing labels are not ready.",
    icon: Sticker,
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

const tileClass = "min-w-0 rounded-xl border border-border bg-gunmetal p-4 md:p-5";
const tileLabelClass = "font-mono text-[10px] uppercase tracking-[0.2em] text-steel";
const tileValueClass = "mt-2 break-words font-display text-2xl font-bold tracking-tight md:text-4xl";
const tileCaptionClass = "mt-1 text-xs text-steel";

export default function AdminDashboardPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);

  const [metrics, setMetrics] = useState<DashboardMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [errorText, setErrorText] = useState("");

  useEffect(() => {
    // A shop switch clears the previous shop's numbers immediately and
    // aborts any in-flight response from that shop.
    const controller = new AbortController();
    setMetrics(null);
    setErrorText("");

    if (!shopId) {
      setLoading(false);
      return () => controller.abort();
    }

    // A new request supersedes every earlier one; its response must never
    // land after a newer request or a shop switch.
    epochRef.current += 1;
    const myEpoch = epochRef.current;
    const requestedShopId = shopId;
    setLoading(true);

    (async () => {
      try {
        const data = await mimirApi.dashboardMetrics({
          shopId: requestedShopId,
          signal: controller.signal,
        });
        if (
          myEpoch !== epochRef.current ||
          !shouldApplyShopResult(requestedShopId, shopIdRef.current) ||
          controller.signal.aborted
        ) {
          return;
        }
        setMetrics({
          inventory_count: data.inventory_count,
          inventory_value: data.inventory_value,
          paperweight_units: data.paperweight_units,
        });
      } catch (err) {
        if (controller.signal.aborted) return;
        if (myEpoch !== epochRef.current) return;
        if (!shouldApplyShopResult(requestedShopId, shopIdRef.current)) return;
        const classified = classifyVendorError(err);
        reportApiError(err);
        setMetrics(null);
        setErrorText(classified.message);
      } finally {
        if (
          !controller.signal.aborted &&
          myEpoch === epochRef.current &&
          shouldApplyShopResult(requestedShopId, shopIdRef.current)
        ) {
          setLoading(false);
        }
      }
    })();

    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  // Loading and error both render "—": a number is shown only once the API
  // returned it, so a failure can never look like a real zero.
  const shown = loading || errorText ? null : metrics;
  const stagnant = shown?.paperweight_units;
  const stagnantWarn = isPositiveMetric(stagnant);

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <PageHeader
        className="mb-6"
        title="Dashboard"
        subtitle={`Vendor home for ${selectedShop?.name}. Live tools are read-only; deferred tools explain themselves.`}
      />

      <section aria-label="Inventory metrics" className="mb-8">
        <h2 className="mb-3 font-mono text-[10px] uppercase tracking-[0.22em] text-steel/70">
          Inventory
        </h2>

        <div aria-live="polite" className="sr-only">
          {loading
            ? "Loading inventory metrics"
            : errorText
              ? `Inventory metrics unavailable. ${errorText}`
              : shown
                ? `${formatMetricCount(shown.inventory_count)} SKUs in stock, inventory value ${formatMetricMoney(shown.inventory_value)} at sell price, ${formatMetricCount(shown.paperweight_units)} stagnant units`
                : ""}
        </div>

        {errorText ? (
          <VendorErrorBanner
            message={`Inventory metrics are unavailable right now. ${errorText}`}
            className="mb-4"
          />
        ) : null}

        <div className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-3" role="status" aria-busy={loading}>
          <div className={tileClass}>
            <p className={tileLabelClass}>In-stock items</p>
            <p className={`${tileValueClass} text-foreground`}>{formatMetricCount(shown?.inventory_count)}</p>
            <p className={tileCaptionClass}>SKUs with stock &gt; 0</p>
          </div>

          <div className={tileClass}>
            <p className={tileLabelClass}>Inventory value</p>
            <p className={`${tileValueClass} text-foreground`}>{formatMetricMoney(shown?.inventory_value)}</p>
            <p className={tileCaptionClass}>At current sell price, not cost</p>
          </div>

          <Link
            href="/admin/paperweight"
            className={`${tileClass} col-span-2 block min-h-11 transition-colors hover:border-neon/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-neon lg:col-span-1`}
          >
            <p className={tileLabelClass}>Stagnant units</p>
            <p className={`${tileValueClass} ${stagnantWarn ? "text-ember" : "text-foreground"}`}>
              {formatMetricCount(stagnant)}
            </p>
            <p className={tileCaptionClass}>Past the paperweight cutoff · open report</p>
          </Link>
        </div>
      </section>

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
        Every number on this page comes from the API. Sales revenue and other
        operational metrics are not shown until their own slices are accepted.
        This page never invents numbers.
      </p>
    </div>
  );
}
