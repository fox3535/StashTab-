export type VendorErrorKind =
  | "session_expired"
  | "forbidden"
  | "conflict"
  | "not_ready"
  | "not_found"
  | "network"
  | "general";

export class VendorApiError extends Error {
  status: number;
  kind: VendorErrorKind;
  code?: string;

  constructor(status: number, message: string, kind: VendorErrorKind, code?: string) {
    super(message);
    this.name = "VendorApiError";
    this.status = status;
    this.kind = kind;
    this.code = code;
  }
}

export function kindFromHttpStatus(status: number, bodyText: string): VendorErrorKind {
  const lowered = bodyText.toLowerCase();
  if (status === 401) return "session_expired";
  if (status === 403) return "forbidden";
  if (status === 409) return "conflict";
  if (status === 404) return "not_found";
  if (status === 503 || lowered.includes("feature_not_ready")) return "not_ready";
  return "general";
}

export function messageForKind(kind: VendorErrorKind, fallback: string): string {
  switch (kind) {
    case "session_expired":
      return "Session expired. Sign in again.";
    case "forbidden":
      return "You do not have access to this shop.";
    case "conflict":
      return "Shop selection required.";
    case "not_ready":
      return "This feature is not ready.";
    case "not_found":
      return "No shop access.";
    case "network":
      return "Network error. Check your connection and try again.";
    default:
      return fallback || "Something went wrong. Try again.";
  }
}

export function classifyVendorError(err: unknown): { kind: VendorErrorKind; message: string } {
  if (err instanceof VendorApiError) {
    return { kind: err.kind, message: err.message };
  }
  if (err && typeof err === "object" && (err as { name?: string }).name === "SessionExpiredError") {
    return { kind: "session_expired", message: messageForKind("session_expired", "") };
  }
  const text = err instanceof Error ? err.message : String(err ?? "");
  const lowered = text.toLowerCase();
  if (
    lowered.includes("failed to fetch") ||
    lowered.includes("networkerror") ||
    lowered.includes("network error")
  ) {
    return { kind: "network", message: messageForKind("network", text) };
  }
  return { kind: "general", message: messageForKind("general", text) };
}

export function vendorErrorFromResponse(status: number, bodyText: string): VendorApiError {
  const kind = kindFromHttpStatus(status, bodyText);
  let code: string | undefined;
  try {
    const parsed = JSON.parse(bodyText) as { error?: string; detail?: string };
    if (typeof parsed.error === "string") code = parsed.error;
  } catch {
    /* plain text */
  }
  if (code === "FEATURE_NOT_READY") {
    return new VendorApiError(status, messageForKind("not_ready", ""), "not_ready", code);
  }
  return new VendorApiError(status, messageForKind(kind, bodyText), kind, code);
}
