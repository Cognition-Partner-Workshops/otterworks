import axios from "axios";
import { Capacitor } from "@capacitor/core";
import { resolveNetworkUrls } from "./network-urls";

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

export const API_BASE_URL = resolveNetworkUrls(
  Capacitor.getPlatform(),
  import.meta.env.VITE_API_BASE_URL,
).api;

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
