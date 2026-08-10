"use client";

import CustomClerkPricing from "@/components/custom-clerk-pricing";
import { Protect } from "@clerk/nextjs";

function UpgradeCard() {
  return (
    <div className="mx-auto max-w-3xl space-y-6 p-6 text-center">
      <h1 className="text-2xl font-semibold lg:text-3xl">Upgrade to StashTab Pro</h1>
      <p className="text-muted-foreground">
        Back-office tools — intake, inventory, Shopify sync, and reports — require a
        paid plan. Show-floor POS stays available on Free.
      </p>
      <CustomClerkPricing />
    </div>
  );
}

export function AdminBillingGate({ children }: { children: React.ReactNode }) {
  const devBypass = Boolean(process.env.NEXT_PUBLIC_DEV_SHOP_ID);

  if (devBypass) {
    return <>{children}</>;
  }

  return (
    <Protect
      condition={(has) => !has({ plan: "free_user" })}
      fallback={<UpgradeCard />}
    >
      {children}
    </Protect>
  );
}
