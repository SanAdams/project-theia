// Pure config helpers for api.ts. No React Native imports, so they run under
// plain Node in tests. api.ts must read each process.env.EXPO_PUBLIC_* var
// literally and pass the value in: Expo only inlines literal member reads.

// Backend base URL for the web build. EXPO_PUBLIC_WEB_API_URL wins when set
// (e.g. the HTTPS Express Mode URL on Amplify); otherwise use port 8000 on the
// host that served the page, which works on localhost and over the LAN.
export function resolveWebApiBaseUrl(
  envUrl: string | undefined,
  hostname: string | undefined,
  fallback: string,
): string {
  const url = envUrl?.trim();
  if (url) return url.replace(/\/+$/, "");
  if (hostname) return `http://${hostname}:8000`;
  return fallback;
}

// Headers for the shared API key. A blank key sends nothing, so local dev
// (backend with API_KEY unset) keeps working.
export function buildAuthHeaders(
  apiKey: string | undefined,
): Record<string, string> {
  const key = apiKey?.trim();
  return key ? { "X-API-Key": key } : {};
}
