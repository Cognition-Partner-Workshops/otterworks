import axios from "axios";
import { Capacitor } from "@capacitor/core";

// ── snake_case → camelCase helpers ────────────────────────────
function snakeToCamel(s: string): string {
  return s.replace(/_([a-z])/g, (_, c) => c.toUpperCase());
}

function transformKeys(obj: unknown): unknown {
  if (Array.isArray(obj)) return obj.map(transformKeys);
  if (obj !== null && typeof obj === "object" && !(obj instanceof Date)) {
    return Object.fromEntries(
      Object.entries(obj as Record<string, unknown>).map(([k, v]) => [
        snakeToCamel(k),
        transformKeys(v),
      ])
    );
  }
  return obj;
}

// Web builds call the same-origin /api/v1 proxy (Vite dev server locally, nginx in
// production) to avoid CORS issues; the proxy forwards /api/v1/* to the API gateway
// (configured via API_GATEWAY_URL env var). Native (Capacitor) builds have no
// same-origin server, so they call the API gateway directly. The local-dev default
// host depends on the platform: the Android emulator reaches the host machine via
// its loopback alias 10.0.2.2, while the iOS Simulator shares the Mac's network
// stack, so the host is plain localhost. Both are plain HTTP by design in local
// dev. Any real deployment must point VITE_API_BASE_URL at an https gateway; the
// scheme below is only the local-dev default.
const WEB_API_BASE_URL = "/api/v1";
const NATIVE_API_SCHEME = "http";
const NATIVE_API_PORT = 8080;
const NATIVE_DEV_HOSTS: Record<string, string> = {
  android: "10.0.2.2",
  ios: "localhost",
};

export function resolveApiBaseUrl(platform: string, override?: string): string {
  if (platform === "web") return WEB_API_BASE_URL;
  if (override) return override;
  const host = NATIVE_DEV_HOSTS[platform] ?? "localhost";
  return `${NATIVE_API_SCHEME}://${host}:${NATIVE_API_PORT}/api/v1`;
}

export const API_BASE_URL = resolveApiBaseUrl(
  Capacitor.getPlatform(),
  import.meta.env.VITE_API_BASE_URL
);

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

apiClient.interceptors.request.use((config) => {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("otter_access_token");
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
  }
  return config;
});

let isVerifyingToken = false;

apiClient.interceptors.response.use(
  (response) => {
    if (response.data) {
      response.data = transformKeys(response.data);
    }
    return response;
  },
  async (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      const url = error.config?.url || "";
      if (!url.includes("/auth/")) {
        if (isVerifyingToken) {
          return Promise.reject(error);
        }
        isVerifyingToken = true;
        try {
          await axios.get(`${API_BASE_URL}/auth/profile`, {
            headers: {
              Authorization: `Bearer ${localStorage.getItem("otter_access_token")}`,
            },
          });
        } catch (verifyError: unknown) {
          const status = (verifyError as { response?: { status?: number } })?.response?.status;
          if (status === 401) {
            localStorage.removeItem("otter_access_token");
            localStorage.removeItem("otter_refresh_token");
            window.location.href = "/login";
          }
        } finally {
          isVerifyingToken = false;
        }
      }
    }
    return Promise.reject(error);
  }
);
