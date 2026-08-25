"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth, useUser } from "@clerk/nextjs";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const API_BASE = process.env.NEXT_PUBLIC_MIMIR_API_URL ?? "http://localhost:8001";

export default function OnboardingPage() {
  const { user, isLoaded } = useUser();
  const { getToken } = useAuth();
  const router = useRouter();
  const [step, setStep] = useState(1);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [storeUrl, setStoreUrl] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [shopId, setShopId] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  async function createShop() {
    if (!user) return;
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      if (!token) {
        throw new Error("Session expired. Sign in again.");
      }
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
      };

      const res = await fetch(`${API_BASE}/api/v1/shops/onboard`, {
        method: "POST",
        headers,
        body: JSON.stringify({
          name,
          slug: slug.toLowerCase().replace(/[^a-z0-9-]/g, "-"),
          clerk_user_id: user.id,
        }),
      });
      if (!res.ok) throw new Error(await res.text());
      const shop = await res.json();
      setShopId(shop.id);
      setStep(2);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create shop");
    } finally {
      setLoading(false);
    }
  }

  async function saveShopify() {
    if (!shopId) return;
    setLoading(true);
    setError("");
    try {
      const token = await getToken();
      if (!token) {
        throw new Error("Session expired. Sign in again.");
      }
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        "X-Shop-Id": shopId,
      };

      if (storeUrl.trim() && apiKey.trim()) {
        const res = await fetch(`${API_BASE}/api/v1/admin/shopify/credentials`, {
          method: "PUT",
          headers,
          body: JSON.stringify({ store_url: storeUrl.trim(), api_key: apiKey.trim() }),
        });
        if (!res.ok) throw new Error(await res.text());
      }
      router.push("/pos");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save Shopify");
    } finally {
      setLoading(false);
    }
  }

  if (!isLoaded) return null;

  return (
    <div className="mx-auto flex min-h-screen max-w-md items-center p-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Welcome to StashTab</CardTitle>
          <p className="text-sm text-muted-foreground">
            Step {step} of 2 — {step === 1 ? "Create your shop" : "Connect Shopify (optional)"}
          </p>
        </CardHeader>
        <CardContent>
          {step === 1 ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                createShop();
              }}
              className="space-y-4"
            >
              <div>
                <Label htmlFor="name">Shop name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value);
                    if (!slug) {
                      setSlug(
                        e.target.value
                          .toLowerCase()
                          .replace(/[^a-z0-9]+/g, "-")
                          .replace(/^-|-$/g, "")
                      );
                    }
                  }}
                  placeholder="My Card Shop"
                  required
                />
              </div>
              <div>
                <Label htmlFor="slug">URL slug</Label>
                <Input
                  id="slug"
                  value={slug}
                  onChange={(e) => setSlug(e.target.value)}
                  placeholder="my-card-shop"
                  required
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button type="submit" className="w-full" disabled={loading || !user}>
                {loading ? "Creating…" : "Continue"}
              </Button>
            </form>
          ) : (
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground">
                Connect Shopify to sync inventory and pull online orders. You can skip and add this later in Settings.
              </p>
              <div>
                <Label htmlFor="store">Store URL</Label>
                <Input
                  id="store"
                  placeholder="your-store.myshopify.com"
                  value={storeUrl}
                  onChange={(e) => setStoreUrl(e.target.value)}
                />
              </div>
              <div>
                <Label htmlFor="key">Admin API token</Label>
                <Input
                  id="key"
                  type="password"
                  placeholder="shpat_…"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                />
              </div>
              {error && <p className="text-sm text-destructive">{error}</p>}
              <Button className="w-full" disabled={loading} onClick={saveShopify}>
                {loading ? "Saving…" : "Finish & open POS"}
              </Button>
              <Button variant="ghost" className="w-full" onClick={() => router.push("/pos")}>
                Skip for now
              </Button>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
