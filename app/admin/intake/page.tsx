"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { toast } from "sonner";
import { adminApi } from "@/lib/admin-api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

export default function AdminIntakePage() {
  const [cardName, setCardName] = useState("");
  const [setName, setSetName] = useState("");
  const [sequenceNumber, setSequenceNumber] = useState("");
  const [lookup, setLookup] = useState<Awaited<
    ReturnType<typeof adminApi.lookupCard>
  > | null>(null);
  const [marketPrice, setMarketPrice] = useState("");
  const [loading, setLoading] = useState(false);

  const [sealedName, setSealedName] = useState("");
  const [sealedSet, setSealedSet] = useState("");
  const [sealedPrice, setSealedPrice] = useState("");
  const [sealedQty, setSealedQty] = useState("1");

  async function handleLookup() {
    if (!setName.trim() || !sequenceNumber.trim()) {
      toast.error("Enter set name and card number");
      return;
    }
    setLoading(true);
    try {
      const result = await adminApi.lookupCard({
        set_name: setName.trim(),
        sequence_number: sequenceNumber.trim(),
        card_name: cardName.trim() || undefined,
      });
      setLookup(result);
      if (result.market_price) setMarketPrice(String(result.market_price));
      toast.success(`Found: ${result.clean_name}`);
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Lookup failed");
      setLookup(null);
    } finally {
      setLoading(false);
    }
  }

  async function handleAddToStaging(cardType: "Single" | "Sealed") {
    setLoading(true);
    try {
      if (cardType === "Single") {
        if (!lookup) return;
        const price = parseFloat(marketPrice) || lookup.market_price || 0;
        if (price <= 0) {
          toast.error("Enter a market price");
          return;
        }
        await adminApi.addToStaging({
          name: lookup.clean_name,
          set_name: lookup.official_set_name || setName,
          sequence_number: lookup.official_set_number || sequenceNumber,
          market_price: price,
          image_url: lookup.high_res_image ?? undefined,
          card_type: "Single",
        });
        setLookup(null);
        setCardName("");
        setSetName("");
        setSequenceNumber("");
        setMarketPrice("");
      } else {
        const price = parseFloat(sealedPrice);
        const qty = parseInt(sealedQty, 10) || 1;
        if (!sealedName.trim() || price <= 0) {
          toast.error("Enter product name and price");
          return;
        }
        await adminApi.addToStaging({
          name: sealedName.trim(),
          set_name: sealedSet.trim() || sealedName.trim(),
          market_price: price,
          quantity: qty,
          card_type: "Sealed",
        });
        setSealedName("");
        setSealedSet("");
        setSealedPrice("");
        setSealedQty("1");
      }
      toast.success("Added to staging dock");
    } catch (e) {
      toast.error(e instanceof Error ? e.message : "Failed to add");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="p-6">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Manual Intake</h1>
          <p className="text-muted-foreground">
            Singles via Pokemon TCG API or sealed products by hand
          </p>
        </div>
        <Link href="/admin/staging">
          <Button variant="outline">Go to Staging →</Button>
        </Link>
      </div>

      <Tabs defaultValue="single">
        <TabsList>
          <TabsTrigger value="single">Single card</TabsTrigger>
          <TabsTrigger value="sealed">Sealed product</TabsTrigger>
        </TabsList>

        <TabsContent value="single" className="mt-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4 rounded-lg border p-4">
              <div>
                <Label>Card name (optional)</Label>
                <Input
                  className="mt-1"
                  placeholder="Charizard ex"
                  value={cardName}
                  onChange={(e) => setCardName(e.target.value)}
                />
              </div>
              <div>
                <Label>Set name</Label>
                <Input
                  className="mt-1"
                  placeholder="Obsidian Flames"
                  value={setName}
                  onChange={(e) => setSetName(e.target.value)}
                />
              </div>
              <div>
                <Label>Card number</Label>
                <Input
                  className="mt-1"
                  placeholder="223/197"
                  value={sequenceNumber}
                  onChange={(e) => setSequenceNumber(e.target.value)}
                />
              </div>
              <Button onClick={handleLookup} disabled={loading}>
                {loading ? "Looking up…" : "Lookup (Pokemon TCG API)"}
              </Button>
            </div>

            <div className="rounded-lg border p-4">
              {lookup ? (
                <div className="space-y-4">
                  <div>
                    <p className="text-lg font-semibold">{lookup.clean_name}</p>
                    <p className="text-sm text-muted-foreground">
                      {lookup.official_set_name} · #{lookup.official_set_number}
                    </p>
                    {lookup.market_price != null && (
                      <p className="mt-2 text-sm">
                        TCG market: ${lookup.market_price.toFixed(2)}
                      </p>
                    )}
                  </div>
                  <div>
                    <Label>Market price ($)</Label>
                    <Input
                      className="mt-1"
                      type="number"
                      step="0.01"
                      value={marketPrice}
                      onChange={(e) => setMarketPrice(e.target.value)}
                    />
                  </div>
                  <Button
                    onClick={() => handleAddToStaging("Single")}
                    disabled={loading}
                  >
                    Add to Staging Dock
                  </Button>
                </div>
              ) : (
                <p className="py-12 text-center text-muted-foreground">
                  Lookup a card to preview price
                </p>
              )}
            </div>
          </div>
        </TabsContent>

        <TabsContent value="sealed" className="mt-6">
          <div className="max-w-md space-y-4 rounded-lg border p-4">
            <div>
              <Label>Product name</Label>
              <Input
                className="mt-1"
                placeholder="151 Elite Trainer Box"
                value={sealedName}
                onChange={(e) => setSealedName(e.target.value)}
              />
            </div>
            <div>
              <Label>Set / line (optional)</Label>
              <Input
                className="mt-1"
                placeholder="Scarlet & Violet 151"
                value={sealedSet}
                onChange={(e) => setSealedSet(e.target.value)}
              />
            </div>
            <div>
              <Label>Market price ($)</Label>
              <Input
                className="mt-1"
                type="number"
                step="0.01"
                value={sealedPrice}
                onChange={(e) => setSealedPrice(e.target.value)}
              />
            </div>
            <div>
              <Label>Quantity</Label>
              <Input
                className="mt-1"
                type="number"
                min={1}
                value={sealedQty}
                onChange={(e) => setSealedQty(e.target.value)}
              />
            </div>
            <Button
              onClick={() => handleAddToStaging("Sealed")}
              disabled={loading}
            >
              Add sealed to Staging
            </Button>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
