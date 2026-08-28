import { redirect } from "next/navigation";

// Slice-04: the starter billing/payment-gated demo page is retired. It
// implied working paid-plan gating (Clerk pricing widget), which StashTab
// does not have. The route now enters the sole authenticated vendor
// dashboard. Clerk protection is preserved by middleware (auth.protect on
// /dashboard(.*)), so the redirect only happens after sign-in. Prior
// location and preserved components: SLICE-04-PRESERVATION.md.
export default function PaymentGatedPage() {
  redirect("/admin/dashboard");
}
