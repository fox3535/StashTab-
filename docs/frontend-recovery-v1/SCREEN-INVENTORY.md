# Screen inventory — current, preserved, partner

Read-only inspection of canonical `main` `6a266b1`. No legacy files were
copied. “Preserved” means still in git history or unmerged branches, not
imported.

Auth today: Clerk middleware on `/dashboard`, `/admin`, `/pos`,
`/onboarding`. API clients send Bearer tokens. Shop is often
`NEXT_PUBLIC_DEV_SHOP_ID` (hint, not membership).

Endpoint classes: **read-ready** = D-029 search/read; **write-disabled** =
exists but fail-closed; **deferred** = later product; **missing** = no
accepted FastAPI contract.

| Screen | Canonical | Preserved / owner / partner | Purpose | Working | Stale / broken | FastAPI | Auth / shop | Endpoint class | Preserve? | Recommend | Tests |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Landing | `app/(marketing)/page.tsx` | Owner marketing copy; no partner equivalent | Public vendor pitch | Public page; Clerk optional if publishable key missing | Frozen staging docs still mention Convex | none | Public | n/a | Owner landing visuals | keep, out of slice-01 | visual + public render |
| Marketing sections | `app/(marketing)/hero-section.tsx` and siblings | Owner | Explain product | Static | Some “all-in-one POS” claims overstate locked writes | none | Public | n/a | Owner motion/brand | keep | visual |
| App shell | `components/product/product-shell.tsx`, header, sidebar | Owner product chrome | Shared admin/POS frame | Layout works | No shop picker; no sign-out; Shopify nav looks live | n/a | Clerk on child routes | n/a | Sidebar IA | **adapt** into one authenticated shell | nav, responsive |
| Dashboard home | `app/dashboard/page.tsx` | Owner dashboard kit | Overview | Renders charts/tables | Sample/demo data, not FastAPI | none | Clerk | missing live reads | layout only | redesign data binding later | empty vs demo |
| Dashboard user | `app/dashboard/nav-user.tsx` | Owner | Account | Opens Clerk profile | **No `signOut()`** | none | Clerk | n/a | profile opener | **adapt**; add explicit sign-out | session expired |
| Dashboard nav | `app/dashboard/nav-main.tsx` | Owner | Nav | Routing | “Quick Create” and Inbox do nothing | none | Clerk | n/a | none of the fake actions | retire fake actions | no dead controls |
| Admin home | `app/admin/page.tsx` | Owner | Admin landing | Shell + billing gate | Second shell vs dashboard | mixed | Clerk + env shop | n/a | gate pattern | merge into one shell | auth gate |
| Inventory | `app/admin/inventory/page.tsx` | Owner list/edit; partner inventory desk | Search and edit cards | Search UI; edit/save present | Writes should be locked; paperweight fetch ignores auth; stale 8001 copy | `GET /admin/inventory`, PATCH item, paperweight | Clerk token; shop hint | search **read-ready**; PATCH **write-disabled** | list/search UX, barcode intent | **adapt** read-only first | empty, search, 401, 403, 503 |
| Intake | `app/admin/intake/page.tsx` | Owner; partner intake | Identify cards | Lookup form | Uses `/admin/intake/lookup` (network identity) not card-resolution slice; staging commit is write | lookup, staging POST | Clerk | lookup **deferred/off**; commit **write-disabled** | form layout | defer commit; later card-resolution | 503 preview |
| Staging | `app/admin/staging/page.tsx` | Owner | Hold before stock | UI | Commit path writes inventory | staging APIs | Clerk | **write-disabled** | hold-queue concept | defer | 503 |
| Resticker | `app/admin/resticker/page.tsx` | Partner resticker | Relabel | UI | Mutates inventory | resticker POSTs | Clerk | **write-disabled** | partner workflow | defer | 503 |
| Paperweight | `app/admin/paperweight/page.tsx` | Owner/partner aging stock | Stale-stock review | UI | May write | paperweight APIs | Clerk | **write-disabled** | rule concept | defer | 503 |
| Import | `app/admin/import/page.tsx` | Owner CSV | Bulk qty | UI | Write/CSV frozen | import | Clerk | **write-disabled** | none live | defer | 503 |
| Reports | `app/admin/reports/page.tsx` | Owner | Reporting | Requests admin | Likely empty/error | admin reports | Clerk | **deferred** | layout | defer | error empty |
| Reconciliation | `app/admin/reconciliation/page.tsx` | Partner recon | Recon | Requests admin | Cutover later | recon | Clerk | **deferred** | partner recon idea | defer | 503 |
| Settings | `app/admin/settings/page.tsx` | Owner; notification branch still has Convex provider | Shop settings | Forms | Shopify creds, pricing writes; notification UI not on `main` | shopify credentials, settings | Clerk | **write-disabled** / notification **deferred** | settings grouping | adapt later | 503 |
| Shopify sync/review | `app/admin/shopify/sync/page.tsx`, `review/page.tsx` | Owner | Channel sync | UI looks operational | Shopify off | shopify admin + mimir | Clerk | **deferred** | do not show as live | defer | hidden or locked |
| Onboarding | `app/onboarding/page.tsx` | Owner | Create shop | POST shop + Shopify creds | Sends `clerk_user_id` in body (hint, not identity); Shopify step | `POST /shops/onboard`, Shopify PUT | Clerk | onboard **exists**; Shopify **deferred** | shop create flow | adapt later | 401/403 |
| POS sell | `app/pos/page.tsx` | Owner mobile POS; partner floor sell | Sell | Cart UI, checkout call | Checkout writes sales/stock | `/inventory/search`, `/sales/checkout` | Clerk | search **read-ready**; checkout **write-disabled** | large-tap cart | keep find; lock sell | 503 on checkout |
| POS find | `app/pos/find/page.tsx` | Owner | Lookup | Search | Same shop-hint issue | `/inventory/search` | Clerk | **read-ready** | fast find | **adapt** | empty search |
| Pulls | `app/pos/pulls/page.tsx` | Owner | Online pulls | UI | Mutates pull state | `/inventory/pulls` | Clerk | **write-disabled** | queue concept | defer | 503 |
| Stats | `app/pos/stats/page.tsx` | Owner | Show stats | UI | Show session writes | show session APIs | Clerk | **deferred** | show-floor stats | defer | 503 |
| POS more | `app/pos/more/page.tsx` | Owner | Extra POS | Sales history | History may 503 | `/sales/history` | Clerk | **deferred** | — | defer | 503 |
| Billing gate | `components/admin-billing-gate.tsx` | Owner Clerk billing | Paywall | Clerk Protect | Not vendor-ops core | Clerk | Clerk | deferred | do not block inventory read | defer | — |
| Notification UI | not on `main` | `origin/feature/backend-notification-v1.1.2` still vendors Convex client | Push settings | — | Do not copy Convex | FastAPI notifications | — | **deferred** | settings IA only, never Convex | defer | — |
| Sign-out | missing | Not found as `signOut()` in canonical or sampled branches | End session | Clerk profile only | Unmerged / absent explicit control | Clerk | Clerk | n/a | explicit sign-out | **add in slice-01** | sign-out + 401 |
| Partner desktop | n/a | `vendor/mimir-partner/` Python app | Floor speed, barcode, recon | Reference | Single-shop, no Clerk | n/a | n/a | n/a | speed, barcode, resticker, recon | preserve behavior via FastAPI | — |

## Partner behavior to preserve (not copy code)

- Fast SKU/name find on the floor.
- Barcode/label and resticker as later write slices.
- Paperweight / aged-stock review as a later read+write slice.
- Reconciliation as later enablement.

## Owner work to preserve

- Product shell, dark vendor visual system, POS layout density.
- Clerk wiring already sending Bearer tokens.
- Landing page brand.

## Do not preserve

- Convex client from the notification branch.
- Demo dashboard tables presented as live data.
- Env-var shop ID as the real shop.
- Dead Quick Create / Inbox.
- Live-looking Shopify nav while Shopify is off.
