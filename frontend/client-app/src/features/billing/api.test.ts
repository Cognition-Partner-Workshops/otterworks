import { afterEach, describe, expect, it, vi } from "vitest";
import { billingApi } from "./api";

afterEach(() => {
  localStorage.clear();
  vi.unstubAllGlobals();
});

describe("signed-in customer billing transport", () => {
  it("forwards the existing access token for entitlement and plan changes", async () => {
    localStorage.setItem("otter_access_token", "customer-access-token");
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetch);
    await billingApi.entitlement("tenant-one", "2026-03-01");
    await billingApi.changePlan("tenant-one", "plan-two", "2026-03-01");
    for (const [, options] of fetch.mock.calls) {
      expect(options.headers.get("Authorization")).toBe("Bearer customer-access-token");
    }
    expect(fetch.mock.calls[1][1].headers.get("Content-Type")).toBe("application/json");
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual({
      plan_id: "plan-two", effective_on: "2026-03-01",
    });
  });

  it("never fabricates credentials for a signed-out request", async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
    vi.stubGlobal("fetch", fetch);
    await billingApi.entitlement("tenant-one", "2026-03-01");
    expect(fetch.mock.calls[0][1].headers.has("Authorization")).toBe(false);
  });
});
