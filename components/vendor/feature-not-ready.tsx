"use client";

export function FeatureNotReady({
  title,
  detail,
}: {
  title: string;
  detail?: string;
}) {
  return (
    <section
      role="status"
      className="m-4 rounded-lg border border-border bg-gunmetal p-6 md:m-6"
    >
      <h2 className="font-display text-lg font-semibold text-foreground">{title}</h2>
      <p className="mt-2 text-sm text-steel">
        {detail || "This feature is not ready. It has not been enabled yet."}
      </p>
    </section>
  );
}

export function LockedNavButton({
  label,
  onExplain,
}: {
  label: string;
  onExplain: () => void;
}) {
  return (
    <button
      type="button"
      aria-disabled="true"
      aria-describedby="locked-nav-reason"
      onClick={onExplain}
      className="flex w-full items-center gap-2 rounded-md border-l-2 border-l-transparent px-2 py-2 text-left text-sm text-steel/80 hover:bg-neon/5 hover:text-foreground"
    >
      <span>{label}</span>
      <span className="ml-auto font-mono text-[10px] uppercase tracking-wider text-steel/60">
        Not ready
      </span>
    </button>
  );
}
