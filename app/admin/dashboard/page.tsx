"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { adminRequest } from "@/lib/admin-api";

type Kpis = {
  inventory_count: number;
  inventory_value: number;
  staging_count: number;
  pending_sync: number;
  total_revenue: number;
  sale_count: number;
  paperweight_units: number;
};

export default function AdminDashboardPage() {
  const [kpis, setKpis] = useState<Kpis | null>(null);

  useEffect(() => {
    adminRequest("/admin/dashboard", { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : null))
      .then(setKpis)
      .catch(() => setKpis(null));
  }, []);

  return (
    <div className="p-6">
      <header className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Dashboard</h1>
          <p className="text-muted-foreground">Shop overview</p>
        </div>
        <Link href="/admin/paperweight" className="text-sm text-primary">
          Paperweight queue →
        </Link>
      </header>

      {kpis ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {[
            { label: "Active SKUs", value: kpis.inventory_count },
            {
              label: "Inventory Value",
              value: `$${Number(kpis.inventory_value).toFixed(0)}`,
            },
            { label: "Staging", value: kpis.staging_count },
            { label: "Pending Sync", value: kpis.pending_sync },
            {
              label: "Total Revenue",
              value: `$${Number(kpis.total_revenue).toFixed(2)}`,
            },
            { label: "Sales", value: kpis.sale_count },
            {
              label: "Paperweight Alert",
              value: `${kpis.paperweight_units ?? 0} units`,
              alert: (kpis.paperweight_units ?? 0) > 0,
            },
          ].map((kpi) => (
            <div
              key={kpi.label}
              className={`rounded-lg border p-4 ${
                "alert" in kpi && kpi.alert ? "border-destructive/50" : ""
              }`}
            >
              <p className="text-sm text-muted-foreground">{kpi.label}</p>
              <p
                className={`text-2xl font-bold ${
                  "alert" in kpi && kpi.alert ? "text-destructive" : ""
                }`}
              >
                {kpi.value}
              </p>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-muted-foreground">
          Set NEXT_PUBLIC_DEV_SHOP_ID and ensure API is running
        </p>
      )}
    </div>
  );
}
