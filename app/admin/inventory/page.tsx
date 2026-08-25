"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { toast } from "sonner";
import { Anchor, Pencil, QrCode, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { adminApi, type InventoryRow } from "@/lib/admin-api";

const API_BASE = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8001";
const PLACEHOLDER =
  "https://placehold.co/50x70/1F1F23/9CA3AF?text=—";

function resolveImageUrl(url: string | null | undefined): string {
  if (!url) return PLACEHOLDER;
  if (url.startsWith("http")) return url;
  const path = url.replace(/\\/g, "/");
  if (path.startsWith("/")) return `${API_BASE}${path}`;
  return path;
}

function apiErrorMessage(err: unknown): string {
  if (!(err instanceof Error)) return "Request failed";
  const raw = err.message;
  try {
    const parsed = JSON.parse(raw) as { detail?: string };
    if (parsed.detail) {
      if (parsed.detail === "Not Found") {
        return "API route not found — restart uvicorn on port 8001 (stale server)";
      }
      return parsed.detail;
    }
  } catch {
    /* plain text */
  }
  return raw;
}

export default function AdminInventoryPage() {
  const { getToken } = useAuth();
  const [q, setQ] = useState("");
  const [items, setItems] = useState<InventoryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState<Partial<InventoryRow>>({});
  const [paperweightIds, setPaperweightIds] = useState<Set<number>>(new Set());

  const auth = useCallback(async () => {
    const token = await getToken();
    if (!token) throw new Error("Session expired. Sign in again.");
    return { authToken: token };
  }, [getToken]);

  async function load() {
    try {
      const a = await auth();
      const data = await adminApi.listInventory({ q, limit: 100 }, a);
      setItems(data.items);
      setTotal(data.total);
    } catch (e) {
      setItems([]);
      toast.error(apiErrorMessage(e));
    }
  }

  useEffect(() => {
    load();
    // Paperweight Rule: cross-reference stagnant 60+ day inventory
    adminApi
      .listPaperweight()
      .then((pw) => setPaperweightIds(new Set(pw.items.map((i) => i.id))))
      .catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function saveEdit(id: number) {
    try {
      const a = await auth();
      await adminApi.updateInventoryItem(
        id,
        {
          stock: draft.stock,
          price: draft.price,
          sticker_price: draft.sticker_price ?? undefined,
        },
        a
      );
      toast.success("Saved");
      setEditing(null);
      await load();
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  async function printLabel(id: number) {
    try {
      const a = await auth();
      const res = await adminApi.generateLabel(id, "QR", a);
      const url = `${API_BASE}${res.image_url}?t=${Date.now()}`;
      const aTag = document.createElement("a");
      aTag.href = url;
      aTag.target = "_blank";
      aTag.rel = "noopener noreferrer";
      document.body.appendChild(aTag);
      aTag.click();
      aTag.remove();
      toast.success(`QR for ${res.sku}`);
    } catch (e) {
      toast.error(apiErrorMessage(e));
    }
  }

  return (
    <div className="p-6">
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
            Inventory Vault
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-steel">
            Desk vault — edit stock/prices and print QR labels. Booth lookup stays on POS → Find
            (read-only).
          </p>
        </div>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel">
          <span className="text-neon">{total}</span> units tracked
        </p>
      </div>

      <div className="mb-4 flex gap-2">
        <Input
          placeholder="Search name, SKU, or set…"
          className="border-border bg-surface font-mono text-sm focus-visible:border-neon focus-visible:shadow-[0_0_16px_rgba(139,92,246,0.25)]"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && load()}
        />
        <Button
          onClick={load}
          className="bg-neon font-display font-bold text-white transition-all duration-200 hover:bg-neon/90 hover:shadow-[0_0_20px_rgba(139,92,246,0.45)]"
        >
          <Search className="size-4" />
          Search
        </Button>
      </div>

      <div className="scrollbar-slim overflow-x-auto rounded-lg border border-border">
        <table className="w-full min-w-[720px] text-sm">
          <thead>
            <tr className="border-b border-border bg-gunmetal">
              <th className="p-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-steel w-16">
                Img
              </th>
              <th className="p-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-steel">
                SKU
              </th>
              <th className="p-3 text-left font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-steel">
                Name
              </th>
              <th className="p-3 text-right font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-steel">
                Stock
              </th>
              <th className="p-3 text-right font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-steel">
                Price
              </th>
              <th className="p-3 text-right font-mono text-[10px] font-medium uppercase tracking-[0.18em] text-steel">
                Sticker
              </th>
              <th className="p-3"></th>
            </tr>
          </thead>
          <tbody>
            {items.map((item, idx) => {
              const stagnant = paperweightIds.has(item.id);
              return (
                <tr
                  key={item.id}
                  className={`border-b border-border/60 border-l-2 border-l-transparent transition-all duration-200 hover:border-l-neon hover:bg-gunmetal ${
                    idx % 2 === 1 ? "bg-row-alt" : "bg-obsidian"
                  }`}
                >
                  <td className="p-3">
                    <div className="relative h-[70px] w-[50px] overflow-hidden rounded border border-border bg-surface">
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={resolveImageUrl(item.image_url)}
                        alt={item.name}
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    </div>
                  </td>
                  <td className="p-3 font-mono text-xs text-steel">{item.sku}</td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-medium text-foreground">{item.name}</span>
                      {stagnant && (
                        <span
                          title="Paperweight Rule: stagnant 60+ days — recover dead capital"
                          className="flex size-4 shrink-0 animate-ember-pulse items-center justify-center rounded-full bg-ember/15"
                        >
                          <Anchor className="size-2.5 text-ember" />
                        </span>
                      )}
                    </div>
                    {item.set_name && (
                      <div className="text-xs text-steel">{item.set_name}</div>
                    )}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-foreground">
                    {editing === item.id ? (
                      <Input
                        type="number"
                        className="ml-auto h-8 w-20 border-border bg-surface font-mono focus-visible:border-neon"
                        value={draft.stock ?? item.stock}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            stock: parseInt(e.target.value, 10),
                          }))
                        }
                      />
                    ) : (
                      item.stock
                    )}
                  </td>
                  <td className="p-3 text-right font-mono text-sm font-semibold text-neon">
                    {editing === item.id ? (
                      <Input
                        type="number"
                        step="0.01"
                        className="ml-auto h-8 w-24 border-border bg-surface font-mono focus-visible:border-neon"
                        value={draft.price ?? item.price}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            price: parseFloat(e.target.value),
                          }))
                        }
                      />
                    ) : (
                      `$${item.price.toFixed(2)}`
                    )}
                  </td>
                  <td className="p-3 text-right font-mono text-sm text-steel">
                    {editing === item.id ? (
                      <Input
                        type="number"
                        step="0.01"
                        className="ml-auto h-8 w-24 border-border bg-surface font-mono focus-visible:border-neon"
                        value={draft.sticker_price ?? item.sticker_price ?? ""}
                        onChange={(e) =>
                          setDraft((d) => ({
                            ...d,
                            sticker_price: parseFloat(e.target.value) || null,
                          }))
                        }
                      />
                    ) : item.sticker_price ? (
                      `$${item.sticker_price.toFixed(2)}`
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="p-3 text-right">
                    {editing === item.id ? (
                      <Button
                        size="sm"
                        className="bg-neon font-semibold text-white hover:bg-neon/90"
                        onClick={() => saveEdit(item.id)}
                      >
                        Save
                      </Button>
                    ) : (
                      <div className="flex justify-end gap-1">
                        <Button
                          size="sm"
                          variant="outline"
                          className="border-border bg-gunmetal text-steel transition-all duration-200 hover:border-neon/50 hover:text-neon"
                          onClick={() => printLabel(item.id)}
                        >
                          <QrCode className="size-3.5" />
                          QR
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className="text-steel transition-colors duration-200 hover:bg-neon/10 hover:text-neon"
                          onClick={() => {
                            setEditing(item.id);
                            setDraft({
                              stock: item.stock,
                              price: item.price,
                              sticker_price: item.sticker_price,
                            });
                          }}
                        >
                          <Pencil className="size-3.5" />
                          Edit
                        </Button>
                      </div>
                    )}
                  </td>
                </tr>
              );
            })}
            {items.length === 0 && (
              <tr>
                <td colSpan={7} className="p-10 text-center font-mono text-sm text-steel">
                  Vault empty for this query — run intake or import to populate.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {paperweightIds.size > 0 && (
        <p className="mt-3 flex items-center gap-2 font-mono text-xs text-steel">
          <span className="flex size-4 animate-ember-pulse items-center justify-center rounded-full bg-ember/15">
            <Anchor className="size-2.5 text-ember" />
          </span>
          {paperweightIds.size} paperweight flag{paperweightIds.size > 1 ? "s" : ""} — stagnant 60+
          days, discount to recover capital
        </p>
      )}
    </div>
  );
}
