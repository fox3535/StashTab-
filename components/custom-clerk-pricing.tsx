'use client'
// Clerk-hosted pricing table only. Not a StashTab payment backend and not Convex.
// Billing defaults off: PricingTable renders only when NEXT_PUBLIC_BILLING_ENABLED
// is explicitly "true", so the public landing never crashes when Clerk billing
// is disabled.
import { PricingTable } from "@clerk/nextjs";
import { dark } from '@clerk/themes'
import { useTheme } from "next-themes"

const BILLING_ENABLED = process.env.NEXT_PUBLIC_BILLING_ENABLED === "true";

function PlansComingSoon() {
    return (
        <div
            role="status"
            aria-live="polite"
            className="mx-auto max-w-xl rounded-lg border border-border bg-surface p-8 text-center"
        >
            <h3 className="font-display text-xl font-semibold text-foreground">
                Plans coming soon
            </h3>
            <p className="mt-2 text-sm leading-relaxed text-steel">
                Self-serve checkout is not enabled yet. StashTab is in early
                access; paid plans open here once billing is enabled.
            </p>
        </div>
    );
}

export default function CustomClerkPricing() {
    const { theme } = useTheme()

    if (!BILLING_ENABLED) {
        return <PlansComingSoon />
    }

    return (
        <>
            <PricingTable
                appearance={{
                    baseTheme: theme === "dark" ? dark : undefined,
                    elements: {
                        pricingTableCardTitle: { // title
                            fontSize: 22,
                            fontWeight: 400,
                        },
                        pricingTableCardDescription: { // description
                            fontSize: 15
                        },
                        pricingTableCardFee: { // price
                            fontSize: 40,
                            fontWeight: 800,  
                        },
                        pricingTable: {
                            gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))',
                        },
                    },
                }}
                
            />
        </>
    )
}