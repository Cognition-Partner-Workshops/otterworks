import { beforeEach, describe, expect, it, vi } from "vitest";

const get = vi.fn();
vi.mock("./api-client", () => ({ apiClient: { get: (...args: unknown[]) => get(...args) } }));

import { searchApi } from "./api";

describe("searchApi", () => {
  beforeEach(() => get.mockReset());

  it("sends q/type and maps camelCased search hits", async () => {
    get.mockResolvedValue({
      data: {
        results: [
          { id: "d1", type: "document", title: "Otter plan", contentSnippet: "<em>otter</em> plan", updatedAt: "2026-10-01T00:00:00Z" },
          { id: "f1", type: "file", name: "otter.png" },
        ],
        total: 2,
        page: 1,
        pageSize: 20,
      },
    });
    const res = await searchApi.search({ query: "otter", type: "document" });
    expect(get).toHaveBeenCalledWith("/search", { params: expect.objectContaining({ q: "otter", type: "document" }) });
    expect(res.data[0]).toMatchObject({ id: "d1", type: "document", name: "Otter plan", snippet: "<em>otter</em> plan" });
    expect(res.data[1]).toMatchObject({ id: "f1", type: "file", name: "otter.png", snippet: "" });
    expect(res.total).toBe(2);
    expect(res.hasMore).toBe(false);
  });

  it("drops the type param for the all filter", async () => {
    get.mockResolvedValue({ data: { results: [], total: 0 } });
    await searchApi.search({ query: "x", type: "all" });
    expect(get.mock.calls[0][1].params.type).toBeUndefined();
  });

  it("computes hasMore from page, pageSize and total", async () => {
    get.mockResolvedValue({ data: { results: [{ id: "a" }], total: 45, page: 1, pageSize: 20 } });
    const res = await searchApi.search({ query: "x" });
    expect(res.hasMore).toBe(true);
    expect(res.data[0].type).toBe("file");
  });

  it("returns suggestions and defaults to empty list", async () => {
    get.mockResolvedValueOnce({ data: { suggestions: ["Otter plan"] } });
    expect(await searchApi.suggest("ot")).toEqual(["Otter plan"]);
    expect(get).toHaveBeenCalledWith("/search/suggest", { params: { q: "ot" } });
    get.mockResolvedValueOnce({ data: {} });
    expect(await searchApi.suggest("ot")).toEqual([]);
  });
});
