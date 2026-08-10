"use client";

import Image from "next/image";
import { useState } from "react";
import { getItemImageUrl, type InventoryItem } from "@/lib/mimir-api";

export function CardThumbnail({
  item,
  size = "md",
}: {
  item: InventoryItem;
  size?: "sm" | "md";
}) {
  const src = getItemImageUrl(item);
  const dims = size === "sm" ? "h-14 w-10" : "h-[70px] w-[50px]";
  const [failed, setFailed] = useState(false);

  if (failed) {
    return (
      <div
        className={`flex ${dims} shrink-0 items-center justify-center rounded-md border border-border bg-surface`}
      >
        <span className="font-mono text-[8px] uppercase tracking-wide text-steel/60">
          {item.game?.slice(0, 3) || "TCG"}
        </span>
      </div>
    );
  }

  return (
    <div
      className={`relative ${dims} shrink-0 overflow-hidden rounded-md border border-border bg-surface`}
    >
      <Image
        src={src}
        alt={item.name}
        fill
        className="object-cover"
        sizes={size === "sm" ? "40px" : "50px"}
        unoptimized
        onError={() => setFailed(true)}
      />
    </div>
  );
}
