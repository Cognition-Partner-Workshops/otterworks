import { beforeEach, describe, expect, it, vi } from "vitest";

const logoutMock = vi.fn();
vi.mock("@/lib/api", () => ({
  authApi: { logout: () => logoutMock() },
}));

import { useAuthStore } from "@/stores/auth-store";

const sampleUser = { id: "u-1", email: "qa@example.test", displayName: "QA User" };

describe("auth store (QA)", () => {
  let originalLocation: Location;

  beforeEach(() => {
    logoutMock.mockReset();
    logoutMock.mockResolvedValue(undefined);
    localStorage.clear();
    useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: true });
    originalLocation = window.location;
  });

  function stubLocation() {
    const fake = { href: "http://localhost:3000/dashboard" } as Location;
    Object.defineProperty(window, "location", { value: fake, writable: true, configurable: true });
    return () =>
      Object.defineProperty(window, "location", {
        value: originalLocation,
        writable: true,
        configurable: true,
      });
  }

  it("starts unauthenticated and loading", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(true);
  });

  it("setUser marks the session authenticated and stops loading", () => {
    useAuthStore.getState().setUser(sampleUser);
    const state = useAuthStore.getState();
    expect(state.user).toEqual(sampleUser);
    expect(state.isAuthenticated).toBe(true);
    expect(state.isLoading).toBe(false);
  });

  it("setUser(null) marks the session unauthenticated", () => {
    useAuthStore.getState().setUser(sampleUser);
    useAuthStore.getState().setUser(null);
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("setLoading toggles only the loading flag", () => {
    useAuthStore.getState().setUser(sampleUser);
    useAuthStore.getState().setLoading(true);
    expect(useAuthStore.getState().isLoading).toBe(true);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("logout clears tokens, resets state, calls the API and redirects to /login", () => {
    const restore = stubLocation();
    try {
      localStorage.setItem("otter_access_token", "a");
      localStorage.setItem("otter_refresh_token", "r");
      useAuthStore.getState().setUser(sampleUser);

      useAuthStore.getState().logout();

      expect(logoutMock).toHaveBeenCalledTimes(1);
      expect(localStorage.getItem("otter_access_token")).toBeNull();
      expect(localStorage.getItem("otter_refresh_token")).toBeNull();
      expect(useAuthStore.getState().user).toBeNull();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
      expect(window.location.href).toBe("/login");
    } finally {
      restore();
    }
  });

  it("logout still clears local session when the API call fails", async () => {
    const restore = stubLocation();
    try {
      logoutMock.mockRejectedValue(new Error("network down"));
      localStorage.setItem("otter_access_token", "a");
      useAuthStore.getState().setUser(sampleUser);

      expect(() => useAuthStore.getState().logout()).not.toThrow();
      await Promise.resolve();

      expect(localStorage.getItem("otter_access_token")).toBeNull();
      expect(useAuthStore.getState().isAuthenticated).toBe(false);
    } finally {
      restore();
    }
  });
});
