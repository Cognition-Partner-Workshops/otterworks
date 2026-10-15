import { describe, it, expect } from "vitest";
import { API_BASE_URL, resolveApiBaseUrl } from "./api-client";

describe("resolveApiBaseUrl", () => {
  it("targets the Android emulator's host alias on android", () => {
    expect(resolveApiBaseUrl("android")).toBe("http://10.0.2.2:8080/api/v1");
  });

  it("targets localhost on ios, where the Simulator shares the Mac's network", () => {
    expect(resolveApiBaseUrl("ios")).toBe("http://localhost:8080/api/v1");
  });

  it("keeps the same-origin proxy path in the browser", () => {
    expect(resolveApiBaseUrl("web")).toBe("/api/v1");
  });

  it("lets VITE_API_BASE_URL override the native default on both platforms", () => {
    const override = "https://api.example.com/api/v1";
    expect(resolveApiBaseUrl("android", override)).toBe(override);
    expect(resolveApiBaseUrl("ios", override)).toBe(override);
  });

  it("ignores the override in the browser, which always uses the proxy", () => {
    expect(resolveApiBaseUrl("web", "https://api.example.com/api/v1")).toBe("/api/v1");
  });

  it("treats an empty override as unset", () => {
    expect(resolveApiBaseUrl("ios", "")).toBe("http://localhost:8080/api/v1");
  });

  it("resolves the browser path for the test (web) runtime", () => {
    expect(API_BASE_URL).toBe("/api/v1");
  });
});
