"use client";

// Slice-11 read-only Inventory Integrity screen.
//
// Replaces the legacy Collectr CSV reconciliation stub (POST upload, CSV
// export, price-drift actions) — none of that behavior is revived.
//
// Backed only by two accepted authenticated read contracts:
//   GET /api/v1/admin/inventory-truth/status   (cutover_status, unaccounted)
//   GET /api/v1/admin/inventory-truth/reconcile (unaccounted_qty, mismatches)
// Both are pure SELECTs scoped by verified Clerk bearer + membership.
// Reconciliation compares inventory snapshots with event-derived truth
// and does not repair anything. The check never runs automatically — it
// runs only through the labeled "Run read-only check" control. Missing,
// timed-out, or unavailable data is stated plainly; no green state is
// invented. Cutover-off stays visible and is neither an error nor an
// approval. No cutover transition, backfill, repair, adjustment, receive,
// sale, CSV, Shopify, notification, payment, or Watch action exists here.

import { useEffect, useRef, useState } from "react";
import {
  mimirApi,
  type InventoryTruthReconcile,
  type InventoryTruthStatus,
} from "@/lib/mimir-api";
import { classifyVendorError } from "@/lib/vendor-api-error";
import { shouldApplyShopResult } from "@/lib/shop-session";
import {
  INTEGRITY_CHECK_TIMEOUT_MS,
  describeCutoverStatus,
  formatMismatchValue,
  reconOutcomeText,
  timedOutNotice,
} from "@/lib/inventory-integrity";
import { useVendorShop } from "@/components/vendor/vendor-shop-provider";
import {
  PageHeader,
  VendorErrorBanner,
  VendorLoadingBlock,
} from "@/components/vendor/vendor-patterns";

type CheckPhase = "idle" | "running" | "done" | "timed_out" | "failed";

/** Mobile/tablet-fallback card. Mirrors the mismatch row, never writes. */
function MismatchCard({
  sku,
  eventRemaining,
  snapshotStock,
}: {
  sku: string;
  eventRemaining: number;
  snapshotStock: number | null;
}) {
  return (
    <div className="rounded-lg border border-border bg-gunmetal p-4">
      <p className="font-mono text-sm font-medium text-foreground">{sku}</p>
      <div className="mt-2 flex flex-wrap items-center gap-4 font-mono text-sm">
        <span className="text-xs text-steel">
          event-derived remaining {formatMismatchValue(eventRemaining)}
        </span>
        <span className="text-xs text-steel">
          snapshot stock {formatMismatchValue(snapshotStock)}
        </span>
      </div>
    </div>
  );
}

export default function InventoryIntegrityPage() {
  const { selectedShop, reportApiError } = useVendorShop();
  const shopId = selectedShop?.id ?? null;
  const shopIdRef = useRef(shopId);
  shopIdRef.current = shopId;
  const epochRef = useRef(0);
  const checkControllerRef = useRef<AbortController | null>(null);

  const [phase, setPhase] = useState<CheckPhase>("idle");
  const [statusResult, setStatusResult] = useState<InventoryTruthStatus | null>(null);
  const [reconResult, setReconResult] = useState<InventoryTruthReconcile | null>(null);
  const [errorText, setErrorText] = useState("");

  // A shop switch clears every previous result immediately and aborts any
  // in-flight check for the previous shop. Nothing auto-runs on mount.
  useEffect(() => {
    setPhase("idle");
    setStatusResult(null);
    setReconResult(null);
    setErrorText("");
    checkControllerRef.current?.abort();
    checkControllerRef.current = null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shopId]);

  useEffect(() => () => checkControllerRef.current?.abort(), []);

  async function runCheck() {
    if (!shopId) return;
    checkControllerRef.current?.abort();
    const controller = new AbortController();
    checkControllerRef.current = controller;

    epochRef.current += 1;
    const myEpoch = epochRef.current;
    const requestedShopId = shopId;
    let timedOut = false;
    const timer = setTimeout(() => {
      timedOut = true;
      controller.abort();
    }, INTEGRITY_CHECK_TIMEOUT_MS);

    setPhase("running");
    setStatusResult(null);
    setReconResult(null);
    setErrorText("");

    try {
      const status = await mimirApi.inventoryTruthStatus({
        shopId: requestedShopId,
        signal: controller.signal,
      });
      const recon = await mimirApi.inventoryTruthReconcile({
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
      setStatusResult(status);
      setReconResult(recon);
      setPhase("done");
    } catch (err) {
      if (
        myEpoch !== epochRef.current ||
        !shouldApplyShopResult(requestedShopId, shopIdRef.current)
      ) {
        return;
      }
      if (timedOut) {
        setStatusResult(null);
        setReconResult(null);
        setPhase("timed_out");
        return;
      }
      if (controller.signal.aborted) return;
      const classified = classifyVendorError(err);
      reportApiError(err);
      setStatusResult(null);
      setReconResult(null);
      setErrorText(classified.message);
      setPhase("failed");
    } finally {
      clearTimeout(timer);
    }
  }

  const mismatchEntries = reconResult ? Object.entries(reconResult.mismatches) : [];
  const shopName = selectedShop?.name ?? "this shop";

  return (
    <div className="w-full max-w-full overflow-x-hidden p-4 md:p-6">
      <PageHeader
        className="mb-5"
        title="Inventory Integrity"
        subtitle={`Read-only cutover status and reconciliation check for ${shopName}. Reconciliation compares inventory snapshots with event-derived truth and does not repair anything.`}
        trailing={
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-steel" role="status">
            {phase === "running" ? (
              <span>checking…</span>
            ) : phase === "done" && reconResult ? (
              <>
                <span className="text-neon">{reconResult.unaccounted_qty}</span>
                {" mismatches"}
              </>
            ) : (
              <span>check not run yet</span>
            )}
          </p>
        }
      />

      <div aria-live="polite" className="sr-only">
        {phase === "running"
          ? "Running read-only inventory integrity check"
          : phase === "timed_out"
            ? timedOutNotice()
            : phase === "failed"
              ? errorText
              : phase === "done" && reconResult
                ? reconOutcomeText(reconResult.unaccounted_qty)
                : "No check has been run yet"}
      </div>

      <section className="mb-4 rounded-lg border border-border bg-gunmetal p-4">
        <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-steel">
          How this check works
        </h2>
        <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-foreground">
          <li>
            It compares the inventory snapshot with event-derived truth, as defined by the
            accepted read-only API contracts. It does not repair, adjust, backfill, or change
            anything.
          </li>
          <li>
            The check never runs automatically. It runs only when you choose the labeled
            control, and it may take some time for shops with many records.
          </li>
          <li>
            Results describe the moment the check ran. No production-readiness score or
            completeness guarantee is claimed.
          </li>
        </ul>
      </section>

      <div className="mb-4 flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={runCheck}
          disabled={phase === "running" || !shopId}
          aria-label="Run read-only inventory integrity check"
          className="min-h-11 rounded-md border border-neon/40 bg-gunmetal px-4 font-mono text-xs uppercase tracking-[0.18em] text-neon focus:outline-none focus-visible:ring-2 focus-visible:ring-neon disabled:cursor-not-allowed disabled:opacity-50"
        >
          Run read-only check
        </button>
        {phase === "idle" ? (
          <p className="text-sm text-steel">
            No check has been run for this shop in this session.
          </p>
        ) : null}
      </div>

      {phase === "failed" ? <VendorErrorBanner message={errorText} className="mb-4" /> : null}

      {phase === "timed_out" ? (
        <p className="mb-4 rounded-lg border border-border bg-gunmetal p-3 font-mono text-xs text-steel">
          {timedOutNotice()}
        </p>
      ) : null}

      {phase === "running" ? (
        <VendorLoadingBlock
          label="Running read-only check…"
          className="h-40 p-3 font-mono text-sm text-steel"
        />
      ) : null}

      {phase === "done" && statusResult && reconResult ? (
        <>
          {/* Cutover status — separate from reconciliation results. */}
          <section className="mb-4 rounded-lg border border-border bg-gunmetal p-4">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-steel">
              Cutover status
            </h2>
            <p className="mt-2 text-sm text-foreground">
              {describeCutoverStatus(statusResult.cutover_status)}
            </p>
          </section>

          {/* Reconciliation results. */}
          <section className="rounded-lg border border-border bg-gunmetal p-4">
            <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-steel">
              Reconciliation result
            </h2>
            <p className="mt-2 text-sm text-foreground">
              {reconOutcomeText(reconResult.unaccounted_qty)}
            </p>

            {mismatchEntries.length > 0 ? (
              <>
                {/* Desktop/tablet table */}
                <div className="mt-3 hidden overflow-x-auto rounded-lg border border-border md:block">
                  <table className="w-full min-w-[640px] text-sm">
                    <thead>
                      <tr className="border-b border-border bg-obsidian">
                        <th className="p-3 text-left font-mono text-[10px] uppercase tracking-[0.18em] text-steel">SKU</th>
                        <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Event-derived remaining</th>
                        <th className="p-3 text-right font-mono text-[10px] uppercase tracking-[0.18em] text-steel">Snapshot stock</th>
                      </tr>
                    </thead>
                    <tbody>
                      {mismatchEntries.map(([sku, mismatch]) => (
                        <tr key={sku} className="border-b border-border/60">
                          <td className="p-3 font-mono text-foreground">{sku}</td>
                          <td className="p-3 text-right font-mono text-steel">
                            {formatMismatchValue(mismatch.event_remaining)}
                          </td>
                          <td className="p-3 text-right font-mono text-foreground">
                            {formatMismatchValue(mismatch.snapshot_stock)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>

                {/* Mobile cards */}
                <div className="mt-3 space-y-2 md:hidden" aria-label="Mismatch rows">
                  {mismatchEntries.map(([sku, mismatch]) => (
                    <MismatchCard
                      key={sku}
                      sku={sku}
                      eventRemaining={mismatch.event_remaining}
                      snapshotStock={mismatch.snapshot_stock}
                    />
                  ))}
                </div>
              </>
            ) : null}
          </section>
        </>
      ) : null}
    </div>
  );
}
