import { redirect } from "next/navigation";

// Slice-03: the stale admin KPI hub is retired. /admin/dashboard is the
// sole authenticated vendor dashboard. Clerk protection is preserved by
// middleware (auth.protect on /admin(.*)).
export default function AdminHome() {
  redirect("/admin/dashboard");
}
