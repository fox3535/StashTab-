"use client";

import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  adminApi,
  type ShopMember,
  type ShopSettings,
  type ShippingRule,
} from "@/lib/admin-api";

export default function AdminSettingsPage() {
  const [settings, setSettings] = useState<ShopSettings | null>(null);
  const [buyPct, setBuyPct] = useState("0.70");
  const [tradePct, setTradePct] = useState("0.80");
  const [roundingStrategy, setRoundingStrategy] = useState(
    "Keep Raw TCG Decimal Payouts"
  );
  const [markupType, setMarkupType] = useState("Percentage (%)");
  const [markupValue, setMarkupValue] = useState("0");
  const [roundingRule, setRoundingRule] = useState("Exact/None");
  const [restickerThreshold, setRestickerThreshold] = useState("2");
  const [priceFluctuation, setPriceFluctuation] = useState("0.10");
  const [paperweightDays, setPaperweightDays] = useState("60");
  const [autoSync, setAutoSync] = useState(false);
  const [omitGraded, setOmitGraded] = useState(false);
  const [fetchingImages, setFetchingImages] = useState(false);

  const [storeUrl, setStoreUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [shopifyConfigured, setShopifyConfigured] = useState(false);
  const [members, setMembers] = useState<ShopMember[]>([]);
  const [inviteUserId, setInviteUserId] = useState("");
  const [saving, setSaving] = useState(false);

  const [rules, setRules] = useState<ShippingRule[]>([]);
  const [ruleMin, setRuleMin] = useState("0");
  const [ruleMax, setRuleMax] = useState("50");
  const [ruleCost, setRuleCost] = useState("1");
  const [ruleType, setRuleType] = useState("Single");

  useEffect(() => {
    adminApi
      .getSettings()
      .then((s) => {
        setSettings(s);
        setBuyPct(String(s.buy_percentage));
        setTradePct(String(s.trade_percentage));
        setRoundingStrategy(s.rounding_strategy);
        setMarkupType(s.markup_type ?? "Percentage (%)");
        setMarkupValue(String(s.markup_value ?? 0));
        setRoundingRule(s.rounding_rule ?? "Exact/None");
        setRestickerThreshold(String(s.resticker_threshold ?? 2));
        setPriceFluctuation(String(s.price_fluctuation_threshold ?? 0.1));
        setPaperweightDays(String(s.paperweight_days ?? 60));
        setAutoSync(Boolean(s.auto_sync_enabled));
        setOmitGraded(Boolean(s.omit_graded_from_recon));
      })
      .catch(() => setSettings(null));

    adminApi
      .getShopifyCredentials()
      .then((c) => {
        setShopifyConfigured(c.configured);
        if (c.store_url) setStoreUrl(c.store_url);
      })
      .catch(() => {});

    adminApi.listMembers().then(setMembers).catch(() => setMembers([]));
    adminApi.listShippingRules().then(setRules).catch(() => setRules([]));
  }, []);

  async function saveSettings() {
    setSaving(true);
    try {
      await adminApi.updateSettings({
        buy_percentage: parseFloat(buyPct),
        trade_percentage: parseFloat(tradePct),
        rounding_strategy: roundingStrategy,
        markup_type: markupType,
        markup_value: parseFloat(markupValue) || 0,
        rounding_rule: roundingRule,
        resticker_threshold: parseFloat(restickerThreshold) || 2,
        price_fluctuation_threshold: parseFloat(priceFluctuation) || 0.1,
        paperweight_days: parseInt(paperweightDays, 10) || 60,
        auto_sync_enabled: autoSync,
        omit_graded_from_recon: omitGraded,
      });
      toast.success("Pricing engine saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function saveShopify() {
    if (!storeUrl.trim() || !apiKey.trim()) {
      toast.error("Store URL and API key required");
      return;
    }
    setSaving(true);
    try {
      await adminApi.saveShopifyCredentials({
        store_url: storeUrl.trim(),
        api_key: apiKey.trim(),
      });
      setShopifyConfigured(true);
      setApiKey("");
      toast.success("Shopify credentials saved");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }

  async function testShopify() {
    try {
      const res = await adminApi.testShopifyConnection();
      toast.success(res.message);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Connection failed");
    }
  }

  async function inviteStaff() {
    if (!inviteUserId.trim()) {
      toast.error("Enter Clerk user ID");
      return;
    }
    try {
      const member = await adminApi.inviteMember({
        clerk_user_id: inviteUserId.trim(),
        role: "staff",
      });
      setMembers((prev) => [...prev, member]);
      setInviteUserId("");
      toast.success("Staff member added");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Invite failed");
    }
  }

  async function addRule() {
    try {
      await adminApi.createShippingRule({
        min_price: parseFloat(ruleMin) || 0,
        max_price: parseFloat(ruleMax) || 0,
        additional_cost: parseFloat(ruleCost) || 0,
        card_type: ruleType,
      });
      setRules(await adminApi.listShippingRules());
      toast.success("Shipping rule added");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  async function removeRule(id: number) {
    try {
      await adminApi.deleteShippingRule(id);
      setRules((prev) => prev.filter((r) => r.id !== id));
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed");
    }
  }

  return (
    <div className="mx-auto max-w-2xl space-y-8 p-6">
      <div>
        <h1 className="text-2xl font-bold">Settings</h1>
        <p className="text-muted-foreground">
          Dynamic pricing engine, Shopify sync, and team
        </p>
      </div>

      <section className="space-y-4 rounded-lg border p-4">
        <h2 className="font-semibold">Buy / trade rates</h2>
        {settings ? (
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Buy percentage</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="1"
                className="mt-1"
                value={buyPct}
                onChange={(e) => setBuyPct(e.target.value)}
              />
            </div>
            <div>
              <Label>Trade percentage</Label>
              <Input
                type="number"
                step="0.01"
                min="0"
                max="1"
                className="mt-1"
                value={tradePct}
                onChange={(e) => setTradePct(e.target.value)}
              />
            </div>
          </div>
        ) : (
          <p className="text-muted-foreground">Loading…</p>
        )}
      </section>

      <section className="space-y-4 rounded-lg border p-4">
        <h2 className="font-semibold">Dynamic pricing engine</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <Label>Sticker rounding strategy</Label>
            <select
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={roundingStrategy}
              onChange={(e) => setRoundingStrategy(e.target.value)}
            >
              <option>Keep Raw TCG Decimal Payouts</option>
              <option>Round Up to Nearest $1.00</option>
              <option>Round to Nearest $1.00</option>
              <option>Round to Nearest $0.95 Cents</option>
            </select>
          </div>
          <div>
            <Label>Shopify markup type</Label>
            <select
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={markupType}
              onChange={(e) => setMarkupType(e.target.value)}
            >
              <option>Percentage (%)</option>
              <option>Flat Amount ($)</option>
            </select>
          </div>
          <div>
            <Label>Markup value</Label>
            <Input
              type="number"
              step="0.01"
              className="mt-1"
              value={markupValue}
              onChange={(e) => setMarkupValue(e.target.value)}
            />
          </div>
          <div>
            <Label>Shopify rounding rule</Label>
            <select
              className="mt-1 w-full rounded-md border bg-background px-3 py-2 text-sm"
              value={roundingRule}
              onChange={(e) => setRoundingRule(e.target.value)}
            >
              <option>Exact/None</option>
              <option>Round to nearest .99</option>
              <option>Round to nearest .50</option>
            </select>
          </div>
          <div>
            <Label>Resticker threshold ($)</Label>
            <Input
              type="number"
              step="0.01"
              className="mt-1"
              value={restickerThreshold}
              onChange={(e) => setRestickerThreshold(e.target.value)}
            />
          </div>
          <div>
            <Label>Price fluctuation threshold</Label>
            <Input
              type="number"
              step="0.01"
              className="mt-1"
              value={priceFluctuation}
              onChange={(e) => setPriceFluctuation(e.target.value)}
            />
          </div>
          <div>
            <Label>Paperweight days</Label>
            <Input
              type="number"
              className="mt-1"
              value={paperweightDays}
              onChange={(e) => setPaperweightDays(e.target.value)}
            />
          </div>
          <div className="flex items-end gap-2 pb-1">
            <input
              id="auto-sync"
              type="checkbox"
              checked={autoSync}
              onChange={(e) => setAutoSync(e.target.checked)}
            />
            <Label htmlFor="auto-sync">Auto-sync worker enabled</Label>
          </div>
          <div className="flex items-end gap-2 pb-1">
            <input
              id="omit-graded"
              type="checkbox"
              checked={omitGraded}
              onChange={(e) => setOmitGraded(e.target.checked)}
            />
            <Label htmlFor="omit-graded">Omit graded cards from Collectr price sync</Label>
          </div>
        </div>
        <Button onClick={saveSettings} disabled={saving}>
          Save pricing engine
        </Button>
      </section>

      <section className="space-y-4 rounded-lg border p-4">
        <h2 className="font-semibold">Inventory images</h2>
        <p className="text-sm text-muted-foreground">
          Match inventory cards against the Pokemon TCG API and download missing
          high-res thumbnails (partner Validate &amp; Fetch Images).
        </p>
        <Button
          variant="outline"
          disabled={fetchingImages}
          onClick={async () => {
            setFetchingImages(true);
            try {
              const res = await adminApi.validateFetchImages();
              toast.success(
                `Checked ${res.checked}: updated ${res.updated}, skipped ${res.skipped}, failed ${res.failed}`
              );
            } catch (e) {
              toast.error(e instanceof Error ? e.message : "Image fetch failed");
            } finally {
              setFetchingImages(false);
            }
          }}
        >
          {fetchingImages ? "Fetching…" : "Validate & fetch images"}
        </Button>
      </section>

      <section className="space-y-4 rounded-lg border p-4">
        <h2 className="font-semibold">Shipping / listing padding rules</h2>
        <p className="text-sm text-muted-foreground">
          Add cost by market price band for singles, sealed, or graded before
          Shopify markup.
        </p>
        <ul className="space-y-2 text-sm">
          {rules.map((r) => (
            <li
              key={r.id}
              className="flex items-center justify-between border-b py-2"
            >
              <span>
                {r.card_type}: ${r.min_price}–${r.max_price} → +$
                {r.additional_cost}
              </span>
              <Button size="sm" variant="ghost" onClick={() => removeRule(r.id)}>
                Remove
              </Button>
            </li>
          ))}
          {!rules.length && (
            <li className="text-muted-foreground">No shipping rules yet</li>
          )}
        </ul>
        <div className="grid gap-2 sm:grid-cols-4">
          <Input
            placeholder="Min $"
            value={ruleMin}
            onChange={(e) => setRuleMin(e.target.value)}
          />
          <Input
            placeholder="Max $"
            value={ruleMax}
            onChange={(e) => setRuleMax(e.target.value)}
          />
          <Input
            placeholder="Add $"
            value={ruleCost}
            onChange={(e) => setRuleCost(e.target.value)}
          />
          <select
            className="rounded-md border bg-background px-3 py-2 text-sm"
            value={ruleType}
            onChange={(e) => setRuleType(e.target.value)}
          >
            <option>Single</option>
            <option>Sealed</option>
            <option>Graded</option>
          </select>
        </div>
        <Button variant="outline" onClick={addRule}>
          Add rule
        </Button>
      </section>

      <section className="space-y-4 rounded-lg border p-4">
        <h2 className="font-semibold">Shopify credentials</h2>
        <p className="text-sm text-muted-foreground">
          {shopifyConfigured
            ? "Credentials configured. Enter a new key to rotate."
            : "Connect your Shopify store for order pulls and inventory sync."}
        </p>
        <div>
          <Label htmlFor="store-url">Store URL</Label>
          <Input
            id="store-url"
            className="mt-1"
            placeholder="your-store.myshopify.com"
            value={storeUrl}
            onChange={(e) => setStoreUrl(e.target.value)}
          />
        </div>
        <div>
          <Label htmlFor="api-key">Admin API access token</Label>
          <Input
            id="api-key"
            type="password"
            className="mt-1"
            placeholder="shpat_…"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
          />
        </div>
        <div className="flex gap-2">
          <Button onClick={saveShopify} disabled={saving}>
            Save Shopify
          </Button>
          {shopifyConfigured && (
            <Button variant="outline" onClick={testShopify}>
              Test connection
            </Button>
          )}
        </div>
      </section>

      <section className="space-y-4 rounded-lg border p-4">
        <h2 className="font-semibold">Team members</h2>
        <ul className="space-y-2 text-sm">
          {members.map((m) => (
            <li key={m.id} className="flex justify-between border-b py-2">
              <span className="font-mono text-xs">{m.clerk_user_id}</span>
              <span className="text-muted-foreground">{m.role}</span>
            </li>
          ))}
          {!members.length && (
            <li className="text-muted-foreground">No members listed</li>
          )}
        </ul>
        <div className="flex gap-2">
          <Input
            placeholder="Clerk user ID (user_…)"
            value={inviteUserId}
            onChange={(e) => setInviteUserId(e.target.value)}
          />
          <Button variant="outline" onClick={inviteStaff}>
            Invite staff
          </Button>
        </div>
      </section>
    </div>
  );
}
