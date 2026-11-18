import axios from "axios";
import * as ImageManipulator from "expo-image-manipulator";
import { Platform } from "react-native";
import { InventoryItem } from "../../App";
import {
  buildAuthHeaders,
  missingWebApiUrlWarning,
  resolveWebApiBaseUrl,
} from "./apiConfig";

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000";

// On web: EXPO_PUBLIC_WEB_API_URL when set (deployed backend), else port 8000
// on the host the browser loaded the app from (localhost or LAN IP).
// Read env vars literally here: Expo only inlines literal process.env.EXPO_PUBLIC_* reads.
const WEB_API_BASE_URL = resolveWebApiBaseUrl(
  process.env.EXPO_PUBLIC_WEB_API_URL,
  typeof window !== "undefined" ? window.location?.hostname : undefined,
  API_BASE_URL,
);

if (Platform.OS === "web") {
  const warning = missingWebApiUrlWarning(
    process.env.EXPO_PUBLIC_WEB_API_URL,
    typeof window !== "undefined" ? window.location?.protocol : undefined,
  );
  if (warning) console.warn(warning);
}

// X-API-Key header when EXPO_PUBLIC_API_KEY is set; empty otherwise.
const AUTH_HEADERS = buildAuthHeaders(process.env.EXPO_PUBLIC_API_KEY);

const client = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30_000,
  headers: AUTH_HEADERS,
});

// Resolves to the correct base URL for the current platform.
// Use this when constructing URLs to backend assets (e.g. barcode images).
export const resolvedApiBaseUrl =
  Platform.OS === "web" ? WEB_API_BASE_URL : API_BASE_URL;

export interface ScanResult {
  items: InventoryItem[];
  total_boxes: number;
}

const HEIC_MIME_TYPES = new Set(["image/heic", "image/heif"]);

async function normalizeUri(uri: string, mimeType?: string): Promise<string> {
  if (!HEIC_MIME_TYPES.has(mimeType ?? "")) return uri;
  const result = await ImageManipulator.manipulateAsync(uri, [], {
    compress: 0.95,
    format: ImageManipulator.SaveFormat.JPEG,
  });
  return result.uri;
}

export async function scanImage(
  imageUri: string,
  mimeType?: string,
): Promise<ScanResult> {
  if (Platform.OS === "web") {
    // On web, use native browser fetch directly — axios's adapter has issues with
    // FormData uploads in the Metro/Expo web bundle (response.body undefined).
    // Send as-is; backend handles HEIC conversion server-side.
    const blobRes = await fetch(imageUri);
    const blob = await blobRes.blob();
    const form = new FormData();
    form.append("file", blob, "scan.jpg");
    // Let the browser set Content-Type + boundary automatically by omitting the header.
    const res = await fetch(`${WEB_API_BASE_URL}/api/v1/scan`, {
      method: "POST",
      headers: AUTH_HEADERS,
      body: form,
    });
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Server error ${res.status}: ${text}`);
    }
    return res.json() as Promise<ScanResult>;
  }

  // Native: convert HEIC → JPEG before upload (smaller payload, correct MIME).
  const uri = await normalizeUri(imageUri, mimeType);
  const formData = new FormData();
  formData.append("file", {
    uri,
    type: "image/jpeg",
    name: "scan.jpg",
  } as unknown as Blob);

  const response = await client.post<ScanResult>("/api/v1/scan", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });

  return response.data;
}
