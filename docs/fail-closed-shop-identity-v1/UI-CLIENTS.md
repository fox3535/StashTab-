# UI clients and Clerk tokens

Production FastAPI rejects caller-supplied shop/user headers. The browser
must send a Clerk Bearer token. `X-Shop-Id` is only the active-shop
selection hint.

## Updated in this slice

Onboarding, POS shop resolve, dashboard, reports, reconciliation, Shopify
review/sync, settings, intake, staging, resticker, paperweight, inventory,
import, notification settings.

## Still using the shared shop hint from `NEXT_PUBLIC_DEV_SHOP_ID`

POS and admin do not yet have a multi-shop picker. The hint is the env
shop id (or `/shops/me` when the user has membership). A later UI slice
should let a multi-shop user pick the active shop without changing API
policy.

Health checks stay unauthenticated.
