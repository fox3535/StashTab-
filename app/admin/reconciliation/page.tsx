"use client";

import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

const API = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8001";
const SHOP_ID = process.env.NEXT_PUBLIC_DEV_SHOP_ID ?? "";

type ReconResult = {
  success?: boolean;
  to_remove: Array<Record<string, unknown>>;
  to_add: Array<Record<string, unknown>>;
  missing_from_collectr?: Array<Record<string, unknown>>;
  removal_list?: Array<{ set?: string; items?: Array<Record<string, unknown>> }>;
  prices_updated?: number;
  updated_items_log?: string[];
  matches_found?: number;
  staged_unknown?: number;
  unknown_cards?: Array<Record<string, unknown>>;
};

export default function ReconciliationPage() {
  const [result, setResult] = useState<ReconResult | null>(null);
  const [sinceDate, setSinceDate] = useState("");
  const [loading, setLoading] = useState(false);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file || !SHOP_ID) return;
    setLoading(true);
    try {
      const form = new FormData();
      form.append("file", file);
      const params = new URLSearchParams({ stage_unknown: "true" });
      if (sinceDate) params.set("since_date", sinceDate);
      const res = await fetch(
        `${API}/api/v1/reports/reconciliation?${params}`,
        {
          method: "POST",
          headers: { "X-Shop-Id": SHOP_ID },
          body: form,
        }
      );
      if (!res.ok) throw new Error(await res.text());
      const data = (await res.json()) as ReconResult;
      setResult(data);
      toast.success(
        `Recon complete — ${data.matches_found ?? 0} removals, ${data.prices_updated ?? 0} price updates`
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Reconciliation failed");
    } finally {
      setLoading(false);
    }
  }

  function exportRemovalCsv() {
    if (!result?.to_remove?.length) return;
    const rows = [
      ["name", "set", "sku", "qty"].join(","),
      ...result.to_remove.map((item) =>
        [
          JSON.stringify(String(item.name ?? "")),
          JSON.stringify(String(item.set ?? item.set_name ?? "")),
          JSON.stringify(String(item.sku ?? "")),
          String(item.qty ?? item.quantity ?? 1),
        ].join(",")
      ),
    ];
    const blob = new Blob([rows.join("\n")], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "collectr-removal-list.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  const missing = result?.missing_from_collectr ?? [];

  return (
    <div className="mx-auto max-w-4xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">Collectr Reconciliation</h1>
        <p className="mt-2 text-muted-foreground">
          Upload a Collectr CSV export. Fuzzy-matches sales for removals, stages
          unknown cards, flags price drift, and lists inventory under-reported in
          Collectr.
        </p>
      </div>

      <div className="flex flex-wrap items-end gap-4">
        <div>
          <Label htmlFor="since">Sales since (optional)</Label>
          <Input
            id="since"
            type="date"
            className="mt-1 w-48"
            value={sinceDate}
            onChange={(e) => setSinceDate(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="csv">Collectr CSV</Label>
          <Input
            id="csv"
            type="file"
            accept=".csv"
            className="mt-1 max-w-sm"
            disabled={loading}
            onChange={handleUpload}
          />
        </div>
      </div>

      {result && (
        <div className="space-y-6">
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" onClick={exportRemovalCsv}>
              Export removal list CSV
            </Button>
          </div>

          <div className="grid gap-4 sm:grid-cols-4">
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Sold → remove</p>
              <p className="text-2xl font-bold">
                {result.matches_found ?? result.to_remove.length}
              </p>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Price updates</p>
              <p className="text-2xl font-bold">{result.prices_updated ?? 0}</p>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Unknown → staging</p>
              <p className="text-2xl font-bold">
                {result.staged_unknown ??
                  result.unknown_cards?.length ??
                  result.to_add.length}
              </p>
            </div>
            <div className="rounded-lg border p-4">
              <p className="text-sm text-muted-foreground">Missing in Collectr</p>
              <p className="text-2xl font-bold">{missing.length}</p>
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <h2 className="font-semibold text-destructive">
                To Remove ({result.to_remove.length})
              </h2>
              <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm">
                {result.to_remove.slice(0, 80).map((item, i) => (
                  <li key={`${item.sku}-${i}`}>
                    {String(item.name)} ({String(item.set ?? "")})
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <h2 className="font-semibold text-primary">
                To Add / Unknown ({result.to_add.length})
              </h2>
              <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm">
                {result.to_add.slice(0, 80).map((item, i) => (
                  <li key={`${item.name}-${i}`}>{String(item.name)}</li>
                ))}
              </ul>
            </div>
          </div>

          {missing.length > 0 && (
            <div>
              <h2 className="font-semibold">
                In vault, under-reported in Collectr ({missing.length})
              </h2>
              <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto text-sm">
                {missing.slice(0, 80).map((item, i) => (
                  <li key={`${item.sku ?? item.name}-${i}`}>
                    {String(item.name ?? item.sku)}
                    {item.set || item.set_name
                      ? ` (${String(item.set ?? item.set_name)})`
                      : ""}
                    {item.stock != null ? ` · stock ${String(item.stock)}` : ""}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {!!result.updated_items_log?.length && (
            <div>
              <h2 className="font-semibold">Price drift log</h2>
              <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto font-mono text-xs text-muted-foreground">
                {result.updated_items_log.map((line) => (
                  <li key={line}>{line}</li>
                ))}
              </ul>
              <p className="mt-2 text-sm text-muted-foreground">
                Approve updates in Admin → Shopify Review.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
