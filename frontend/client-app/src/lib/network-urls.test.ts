import { describe, expect, it } from "vitest";
import { resolveNetworkUrls } from "./network-urls";

describe("network URL defaults", () => {
  it.each([ ["ios", "localhost"], ["android", "10.0.2.2"] ])("uses %s host loopback", (platform, host) => {
    expect(resolveNetworkUrls(platform)).toEqual({ api: `http://${host}:8080/api/v1`, collab: `ws://${host}:8085` });
    expect(resolveNetworkUrls(platform, "", "", "https:")).toEqual(resolveNetworkUrls(platform));
  });

  it.each(["ios", "android"])("honors deployment overrides on %s", (platform) => {
    expect(resolveNetworkUrls(platform, "https://api.example/api/v1", "wss://collab.example")).toEqual({ api: "https://api.example/api/v1", collab: "wss://collab.example" });
  });

  it("preserves web proxy and protocol behavior", () => {
    expect(resolveNetworkUrls("web", "https://ignored.example")).toEqual({ api: "/api/v1", collab: "ws://localhost:8085" });
    expect(resolveNetworkUrls("web", undefined, "", "https:").collab).toBe("wss://localhost:8085");
    expect(resolveNetworkUrls("web", undefined, "wss://override.example").collab).toBe("wss://override.example");
  });
});
