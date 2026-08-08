/**
 * Shared API client for the Digital Campus frontend.
 *
 * Browser sessions authenticate via the HttpOnly session cookie set at
 * login (auto-sent with every same-origin request through the Next.js
 * proxy). A legacy Bearer token kept in localStorage is attached as a
 * fallback for accounts that logged in before the cookie migration, so
 * old sessions keep working until they sign out.
 *
 * State-changing requests carry `X-Requested-With` — the CSRF guard the
 * backend requires for cookie-authenticated mutations.
 */

export function getAuthHeader(): Record<string, string> {
  if (typeof window === "undefined") return {};
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export function getLegacyToken(): string {
  if (typeof window === "undefined") return "";
  return localStorage.getItem("token") || "";
}

export function hasSession(): boolean {
  if (typeof window === "undefined") return false;
  return Boolean(localStorage.getItem("token"));
}

export function signOut(): void {
  if (typeof window === "undefined") return;
  localStorage.removeItem("token");
  localStorage.removeItem("dc_offline_messages");
  // Best-effort cookie clear; the backend clears it on /auth/logout too.
  fetch("/api/v1/auth/logout", { method: "POST" }).catch(() => {});
}

interface ApiFetchOptions extends RequestInit {
  auth?: boolean;
}

/**
 * fetch() wrapper: JSON handling, CSRF header, legacy bearer token.
 * Returns the parsed JSON; throws Error(detail) on non-2xx.
 */
export async function apiFetch<T = any>(
  path: string,
  options: ApiFetchOptions = {}
): Promise<T> {
  const { auth = true, headers = {}, ...rest } = options;

  const mergedHeaders: Record<string, string> = {
    ...(headers as Record<string, string>),
  };
  if (rest.method && rest.method !== "GET") {
    mergedHeaders["X-Requested-With"] = "XMLHttpRequest";
  }
  if (rest.body != null && typeof rest.body === "string" && !mergedHeaders["Content-Type"]) {
    mergedHeaders["Content-Type"] = "application/json";
  }
  if (auth) {
    const legacy = getLegacyToken();
    if (legacy) mergedHeaders["Authorization"] = `Bearer ${legacy}`;
  }

  const res = await fetch(path, { ...rest, headers: mergedHeaders });
  if (res.status === 204) return undefined as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data.detail || `Request failed (${res.status})`);
  }
  return data as T;
}
