# Clerk + Convex auth fix

## Symptom

```
No auth provider found matching the given token
… applicationID: convex
```

Or clicking Login does nothing because you are already signed into Clerk while Convex still rejects the JWT.

## Fix (Clerk Dashboard)

1. Open **JWT Templates** → template named exactly `convex`
2. Set **Claims** to:

```json
{
  "aud": "convex"
}
```

3. Confirm Issuer is `https://fleet-adder-92.clerk.accounts.dev` (or your Frontend API URL)
4. Save → hard refresh the app → **Sign out** → **Sign in** again

`aud` must match `applicationID: "convex"` in [`convex/auth.config.ts`](../convex/auth.config.ts).

## Convex env

```bash
npx convex env set CLERK_JWT_ISSUER_DOMAIN "https://fleet-adder-92.clerk.accounts.dev"
```

Also keep `NEXT_PUBLIC_CLERK_FRONTEND_API_URL` set to the same issuer in `.env.local` and Convex.

## Note

POS and Admin use Clerk + the Python API (`DEV_SHOP_ID` / shop membership). They work even if Convex auth is still noisy. Convex is only required for starter billing/user sync features.
