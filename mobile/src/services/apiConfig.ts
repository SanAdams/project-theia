// Pure config helpers for api.ts. No React Native imports, so they run under
// plain Node in tests. api.ts must read each process.env.EXPO_PUBLIC_* var
// literally and pass the value in: Expo only inlines literal member reads.

// Backend base URL for the web build. EXPO_PUBLIC_WEB_API_URL wins when set
// (e.g. the HTTPS Express Mode URL on Amplify); otherwise use port 8000 on the
// host that served the page, which works on localhost and over the LAN.
// Throws on a value without an http(s) scheme: fetch would otherwise treat it
// as a path relative to the page and fail with a confusing error.
export function resolveWebApiBaseUrl(
  envUrl: string | undefined,
  hostname: string | undefined,
  fallback: string,
): string {
  const url = envUrl?.trim();
  if (url) {
    if (!/^https?:\/\//i.test(url)) {
      throw new Error(
        `EXPO_PUBLIC_WEB_API_URL must start with http:// or https:// (got "${url}")`,
      );
    }
    return url.replace(/\/+$/, "");
  }
  if (hostname) return `http://${hostname}:8000`;
  return fallback;
}

// Warning to log when an HTTPS page has no backend URL configured: the
// http://<hostname>:8000 fallback is blocked as mixed content there, and the
// only visible symptom would be "Failed to fetch". Returns null when fine.
export function missingWebApiUrlWarning(
  envUrl: string | undefined,
  pageProtocol: string | undefined,
): string | null {
  if (pageProtocol !== "https:" || envUrl?.trim()) return null;
  return (
    "EXPO_PUBLIC_WEB_API_URL is not set, so scans will call " +
    "http://<hostname>:8000, which browsers block on an HTTPS page. " +
    "Set it to the backend's HTTPS URL and rebuild."
  );
}

// Headers for the shared API key. A blank key sends nothing, so local dev
// (backend with API_KEY unset) keeps working.
export function buildAuthHeaders(
  apiKey: string | undefined,
): Record<string, string> {
  const key = apiKey?.trim();
  return key ? { "X-API-Key": key } : {};
}
