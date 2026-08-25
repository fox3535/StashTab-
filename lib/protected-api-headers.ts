export class SessionExpiredError extends Error {
  constructor(message = "Session expired. Sign in again.") {
    super(message);
    this.name = "SessionExpiredError";
  }
}

export type ProtectedApiAuth = {
  shopId?: string;
  authToken?: string | null;
};

export function buildProtectedApiHeaders(auth: ProtectedApiAuth): Record<string, string> {
  const token = typeof auth.authToken === "string" ? auth.authToken.trim() : "";
  if (!token) {
    throw new SessionExpiredError();
  }
  const headers: Record<string, string> = {
    Authorization: `Bearer ${token}`,
  };
  if (auth.shopId) {
    headers["X-Shop-Id"] = auth.shopId;
  }
  return headers;
}
