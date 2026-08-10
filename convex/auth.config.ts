export default {
  providers: [
    {
      // Prefer Convex-dashboard env; fall back to Next public name used in .env.local
      domain:
        process.env.CLERK_JWT_ISSUER_DOMAIN ??
        process.env.NEXT_PUBLIC_CLERK_FRONTEND_API_URL,
      applicationID: "convex",
    },
  ],
};
