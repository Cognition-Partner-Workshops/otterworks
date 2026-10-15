import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { billingServer } from "@/test-setup";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

const ACCESS = "qa-access-token";
const REFRESH = "qa-refresh-token";

function seedTokens() {
  localStorage.setItem("otter_access_token", ACCESS);
  localStorage.setItem("otter_refresh_token", REFRESH);
}

function captureAuthHeader(method: "get" | "post", path: string, status = 200) {
  const seen: Array<string | null> = [];
  const factory = method === "get" ? http.get : http.post;
  billingServer.use(
    factory(path, ({ request }) => {
      seen.push(request.headers.get("authorization"));
      return status === 204
        ? new HttpResponse(null, { status })
        : HttpResponse.json({ error: "x" }, { status });
    })
  );
  return seen;
}

describe("api client auth wiring", () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => vi.restoreAllMocks());

  it("attaches the stored access token as a Bearer header", async () => {
    seedTokens();
    const seen = captureAuthHeader("get", "*/api/v1/auth/profile");
    await apiClient.get("/auth/profile");
    expect(seen).toEqual([`Bearer ${ACCESS}`]);
  });

  it("sends no Authorization header when signed out", async () => {
    const seen = captureAuthHeader("get", "*/api/v1/auth/profile");
    await apiClient.get("/auth/profile");
    expect(seen).toEqual([null]);
  });

  it("clears tokens when a protected call 401s and the profile check also 401s", async () => {
    seedTokens();
    captureAuthHeader("get", "*/api/v1/documents/", 401);
    captureAuthHeader("get", "*/api/v1/auth/profile", 401);
    await expect(apiClient.get("/documents/")).rejects.toBeTruthy();
    expect(localStorage.getItem("otter_access_token")).toBeNull();
    expect(localStorage.getItem("otter_refresh_token")).toBeNull();
  });

  it("keeps tokens when a protected call 401s but the profile check succeeds", async () => {
    seedTokens();
    captureAuthHeader("get", "*/api/v1/documents/", 401);
    captureAuthHeader("get", "*/api/v1/auth/profile", 200);
    await expect(apiClient.get("/documents/")).rejects.toBeTruthy();
    expect(localStorage.getItem("otter_access_token")).toBe(ACCESS);
  });

  it("does not clear tokens when an /auth/ call itself 401s (e.g. bad login)", async () => {
    seedTokens();
    captureAuthHeader("post", "*/api/v1/auth/login", 401);
    await expect(apiClient.post("/auth/login", {})).rejects.toBeTruthy();
    expect(localStorage.getItem("otter_access_token")).toBe(ACCESS);
  });
});

describe("auth store logout", () => {
  beforeEach(() => {
    localStorage.clear();
    useAuthStore.setState({
      user: { id: "u1", email: "qa@example.test", displayName: "QA" } as never,
      isAuthenticated: true,
      isLoading: false,
    });
  });

  it("clears tokens and resets the store", async () => {
    seedTokens();
    captureAuthHeader("post", "*/api/v1/auth/logout", 204);
    useAuthStore.getState().logout();
    expect(localStorage.getItem("otter_access_token")).toBeNull();
    expect(localStorage.getItem("otter_refresh_token")).toBeNull();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().user).toBeNull();
  });

  // [REAL] ui-logout-no-token: logout() removes the tokens synchronously before the async
  // axios request interceptor runs, so POST /auth/logout goes out without a Bearer header
  // and auth-service never revokes the refresh token.
  it.fails("sends the access token to POST /auth/logout so the server can revoke it", async () => {
    seedTokens();
    const seen = captureAuthHeader("post", "*/api/v1/auth/logout", 204);
    useAuthStore.getState().logout();
    await vi.waitFor(() => expect(seen.length).toBe(1));
    expect(seen[0]).toBe(`Bearer ${ACCESS}`);
  });
});
