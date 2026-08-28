"use client";

// Shared vendor-core presentation patterns (F1 vendor-core batch).
//
// Extracted only where at least two accepted pages already duplicated the
// same behaviour: page headers (dashboard/inventory/find), gate state
// panels (shop access gate + onboarding), error banners and loading blocks
// (inventory + find), and offset pagination for the accepted
// GET /api/v1/inventory/search browse (inventory + find). Behaviour and
// visual identity are preserved — these are the same classes and strings
// the pages already rendered.

import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { FindPageWindow } from "@/lib/pos-find";

export function PageHeader({
  title,
  subtitle,
  trailing,
  className,
}: {
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-end justify-between gap-3", className)}>
      <div>
        <h1 className="font-display text-2xl font-bold tracking-tight text-foreground">
          {title}
        </h1>
        {subtitle ? <p className="mt-1 max-w-2xl text-sm text-steel">{subtitle}</p> : null}
      </div>
      {trailing}
    </div>
  );
}

export function VendorStatePanel({
  role = "status",
  title,
  detail,
  className,
  children,
}: {
  role?: "status" | "alert";
  title: string;
  detail?: string;
  className?: string;
  children?: ReactNode;
}) {
  return (
    <section role={role} className={cn("m-4 rounded-lg border border-border bg-gunmetal p-6", className)}>
      <h2 className="font-display text-lg font-semibold">{title}</h2>
      {detail ? <p className="mt-2 text-sm text-steel">{detail}</p> : null}
      {children}
    </section>
  );
}

export function VendorErrorBanner({
  message,
  className,
}: {
  message: string;
  className?: string;
}) {
  return (
    <p role="alert" className={cn("rounded-md border border-border bg-gunmetal p-3 text-sm text-steel", className)}>
      {message}
    </p>
  );
}

export function VendorLoadingBlock({
  label,
  className,
}: {
  label: string;
  className?: string;
}) {
  return (
    <div
      role="status"
      className={cn("animate-pulse rounded-lg bg-gunmetal motion-reduce:animate-none", className)}
    >
      {label}
    </div>
  );
}

/**
 * Offset pagination for the accepted inventory search contract. The window
 * comes from the slice-05 findPageWindow helper so boundaries always track
 * the honest contract total, never the page length.
 */
export function BrowsePagination({
  windowInfo,
  total,
  onPrev,
  onNext,
  disabled = false,
  buttonClassName = "min-h-11",
  className,
}: {
  windowInfo: FindPageWindow;
  total: number;
  onPrev: () => void;
  onNext: () => void;
  disabled?: boolean;
  buttonClassName?: string;
  className?: string;
}) {
  return (
    <nav aria-label="Result pages" className={cn("flex flex-wrap items-center gap-3", className)}>
      <Button
        variant="outline"
        className={cn("border-border font-mono text-sm", buttonClassName)}
        onClick={onPrev}
        disabled={!windowInfo.hasPrev || disabled}
        aria-label="Previous results page"
      >
        ← Previous
      </Button>
      <span className="font-mono text-sm text-steel">
        {windowInfo.from}–{windowInfo.to} of {total}
      </span>
      <Button
        variant="outline"
        className={cn("border-border font-mono text-sm", buttonClassName)}
        onClick={onNext}
        disabled={!windowInfo.hasNext || disabled}
        aria-label="Next results page"
      >
        Next →
      </Button>
      {windowInfo.endOfResults ? (
        <span className="font-mono text-xs text-steel/80">End of results.</span>
      ) : null}
    </nav>
  );
}
