import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { billingServer as server } from "../test-setup";
import { apiClient, API_BASE_URL } from "@/lib/api-client";
import { authApi } from "@/lib/api";

const base = "http://localhost:3000/api/v1";

describe("api client auth wiring (QA)", () => {
  let originalLocation: Location;

  beforeEach(() => {
    localStorage.clear();
    originalLocation = window.location;
    Object.defineProperty(window, "location", {
      value: { href: "http://localhost:3000/dashboard" },
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(window, "location", {
      value: originalLocation,
      writable: true,
      configurable: true,
    });
  });

  it("uses the same-origin /api/v1 proxy on web", () => {
    expect(API_BASE_URL).toBe("/api/v1");
  });

  it("attaches the stored access token as a Bearer header", async () => {
    let seen: string | null = null;
    server.use(
      http.get(`${base}/auth/profile`, ({ request }) => {
        seen = request.headers.get("authorization");
        return HttpResponse.json({ id: "1", email: "a@b.test", display_name: "A" });
      })
    );
    localStorage.setItem("otter_access_token", "tok-123");
    await apiClient.get("/auth/profile");
    expect(seen).toBe("Bearer tok-123");
  });

  it("omits the Authorization header when no token is stored", async () => {
    let seen: string | null = "unset";
    server.use(
      http.get(`${base}/auth/profile`, ({ request }) => {
        seen = request.headers.get("authorization");
        return HttpResponse.json({});
      })
    );
    await apiClient.get("/auth/profile");
    expect(seen).toBeNull();
  });

  it("camelCases snake_case response keys", async () => {
    server.use(
      http.get(`${base}/auth/profile`, () =>
        HttpResponse.json({ id: "1", display_name: "QA", avatar_url: null })
      )
    );
    const user = await authApi.getProfile();
    expect(user.displayName).toBe("QA");
  });

  it("clears tokens and redirects to /login when a protected call 401s and the token is invalid", async () => {
    server.use(
      http.get(`${base}/documents`, () => HttpResponse.json({ error: "x" }, { status: 401 })),
      http.get(`${base}/auth/profile`, () => HttpResponse.json({ error: "x" }, { status: 401 }))
    );
    localStorage.setItem("otter_access_token", "expired");
    localStorage.setItem("otter_refresh_token", "refresh");
    await expect(apiClient.get("/documents")).rejects.toBeTruthy();
    expect(localStorage.getItem("otter_access_token")).toBeNull();
    expect(localStorage.getItem("otter_refresh_token")).toBeNull();
    expect(window.location.href).toBe("/login");
  });

  it("keeps the session when a protected call 401s but the profile check succeeds", async () => {
    server.use(
      http.get(`${base}/documents`, () => HttpResponse.json({ error: "x" }, { status: 401 })),
      http.get(`${base}/auth/profile`, () => HttpResponse.json({ id: "1" }))
    );
    localStorage.setItem("otter_access_token", "still-valid");
    await expect(apiClient.get("/documents")).rejects.toBeTruthy();
    expect(localStorage.getItem("otter_access_token")).toBe("still-valid");
    expect(window.location.href).toBe("http://localhost:3000/dashboard");
  });

  it("does not redirect on a 401 from an /auth/ endpoint (e.g. bad login)", async () => {
    server.use(
      http.post(`${base}/auth/login`, () =>
        HttpResponse.json({ message: "Invalid credentials" }, { status: 401 })
      )
    );
    await expect(authApi.login({ email: "a@b.test", password: "nope" })).rejects.toBeTruthy();
    expect(window.location.href).toBe("http://localhost:3000/dashboard");
  });

  it("does not redirect on non-401 errors", async () => {
    server.use(
      http.get(`${base}/documents`, () => HttpResponse.json({ error: "x" }, { status: 403 }))
    );
    localStorage.setItem("otter_access_token", "tok");
    await expect(apiClient.get("/documents")).rejects.toBeTruthy();
    expect(localStorage.getItem("otter_access_token")).toBe("tok");
  });

  it("register only sends displayName/email/password (no confirmPassword)", async () => {
    let body: unknown = null;
    server.use(
      http.post(`${base}/auth/register`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ access_token: "a", refresh_token: "r" }, { status: 201 });
      })
    );
    const tokens = await authApi.register({
      displayName: "QA",
      email: "qa@example.test",
      password: "Passw0rd!23",
      confirmPassword: "Passw0rd!23",
    } as never);
    expect(body).toEqual({ displayName: "QA", email: "qa@example.test", password: "Passw0rd!23" });
    expect(tokens.accessToken).toBe("a");
  });

  it("logout posts to /auth/logout with the bearer token", async () => {
    let seen: string | null = null;
    server.use(
      http.post(`${base}/auth/logout`, ({ request }) => {
        seen = request.headers.get("authorization");
        return new HttpResponse(null, { status: 204 });
      })
    );
    localStorage.setItem("otter_access_token", "tok-logout");
    await authApi.logout();
    expect(seen).toBe("Bearer tok-logout");
  });
});
