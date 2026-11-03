import { afterEach, describe, expect, it, vi } from "vitest";
import { call, HttpError } from "./client";

const respond = (status: number, body?: unknown) =>
  vi.fn(async () => new Response(body === undefined ? null : JSON.stringify(body), { status }));

afterEach(() => vi.unstubAllGlobals());

describe("call", () => {
  it("hits the same-origin /api proxy without caching and sends JSON bodies", async () => {
    const f = respond(200, { ok: true });
    vi.stubGlobal("fetch", f);
    await expect(call("/bags", { method: "POST", body: { a: 1 } })).resolves.toEqual({ ok: true });
    const [url, init] = f.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/bags");
    expect(init.cache).toBe("no-store");
    expect(init.body).toBe('{"a":1}');
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
  });
  it("returns undefined for 204", async () => {
    vi.stubGlobal("fetch", respond(204));
    await expect(call("/auth/logout", { method: "POST" })).resolves.toBeUndefined();
  });
  it("surfaces the API error code and message", async () => {
    vi.stubGlobal("fetch", respond(409, { error: "OUT_OF_STOCK", message: "Some items in your bag sold out." }));
    const err = await call("/checkout").catch((e) => e);
    expect(err).toBeInstanceOf(HttpError);
    expect(err).toMatchObject({ status: 409, code: "OUT_OF_STOCK", message: "Some items in your bag sold out." });
  });
  it("falls back to a generic message when the body is not JSON", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => new Response("<html>bad gateway</html>", { status: 502 })));
    await expect(call("/products")).rejects.toMatchObject({ status: 502, code: "ERROR", message: "Something went wrong. Please try again." });
  });
});
