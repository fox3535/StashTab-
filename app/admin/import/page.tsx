"use client";

import { useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { adminApi } from "@/lib/admin-api";

export default function AdminImportPage() {
  const { getToken, userId } = useAuth();
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Record<string, number | boolean> | null>(null);

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setLoading(true);
    try {
      const token = await getToken();
      const data = await adminApi.importCsv(file, {
        authToken: token,
        clerkUserId: userId,
      });
      setResult(data);
      toast.success(`Import done — ${data.imported} new, ${data.updated} updated`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Import failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-6 p-6">
      <div>
        <h1 className="text-2xl font-bold">CSV Import</h1>
        <p className="mt-2 text-muted-foreground">
          Import Collectr or vendor CSV exports into inventory. Supports Pokemon,
          One Piece, sealed products, and graded cards.
        </p>
      </div>
      <input
        type="file"
        accept=".csv"
        disabled={loading}
        onChange={handleUpload}
        className="block w-full max-w-md text-sm"
      />
      {result && (
        <dl className="grid grid-cols-2 gap-3 rounded-lg border p-4 text-sm">
          <div>
            <dt className="text-muted-foreground">Imported</dt>
            <dd className="text-xl font-bold">{result.imported}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Updated</dt>
            <dd className="text-xl font-bold">{result.updated}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Needs review</dt>
            <dd className="text-xl font-bold">{result.needs_review}</dd>
          </div>
          <div>
            <dt className="text-muted-foreground">Errors</dt>
            <dd className="text-xl font-bold">{result.errors}</dd>
          </div>
        </dl>
      )}
      {loading && <p className="text-sm text-muted-foreground">Importing…</p>}
    </div>
  );
}
