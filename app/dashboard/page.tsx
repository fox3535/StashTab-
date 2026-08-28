import { redirect } from "next/navigation";

// Slice-03: the starter/demo dashboard is retired from routing. Its
// components remain in this folder (see SLICE-03-PRESERVATION.md).
// /admin/dashboard is the sole authenticated vendor dashboard. Clerk
// protection is preserved by middleware (auth.protect on /dashboard(.*)).
export default function Page() {
  redirect("/admin/dashboard");
}
