import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { searchApi } from "./api";
import { billingServer } from "../test-setup";

const SEARCH_URL = "http://localhost:3000/api/v1/search";

function captureSearch(body: Record<string, unknown>) {
  const seen: URL[] = [];
  billingServer.use(
    http.get(SEARCH_URL, ({ request }) => {
      seen.push(new URL(request.url));
      return HttpResponse.json(body);
    })
  );
  return seen;
}

describe("searchApi.search (QA)", () => {
  it("maps document hits into SearchResult rows", async () => {
    captureSearch({
      results: [
        {
          id: "d1",
          type: "document",
          title: "Otter Plan",
          content_snippet: "the <em>otter</em> plan",
          updated_at: "2026-01-01T00:00:00Z",
        },
      ],
      total: 1,
      page: 1,
      page_size: 20,
      query: "otter",
    });
    const res = await searchApi.search({ query: "otter" });
    expect(res.data).toEqual([
      {
        id: "d1",
        type: "document",
        name: "Otter Plan",
        snippet: "the <em>otter</em> plan",
        path: "",
        updatedAt: "2026-01-01T00:00:00Z",
        ownerName: "",
      },
    ]);
    expect(res.total).toBe(1);
    expect(res.pageSize).toBe(20);
    expect(res.hasMore).toBe(false);
  });

  it("falls back to name for file hits and defaults type to file", async () => {
    captureSearch({ results: [{ id: "f1", name: "report.pdf" }], total: 1 });
    const [row] = (await searchApi.search({ query: "report" })).data;
    expect(row.name).toBe("report.pdf");
    expect(row.type).toBe("file");
    expect(row.snippet).toBe("");
  });

  it("computes hasMore from total/page/pageSize", async () => {
    captureSearch({ results: [{ id: "a", title: "a" }], total: 45, page: 2, page_size: 20 });
    const res = await searchApi.search({ query: "a" });
    expect(res.page).toBe(2);
    expect(res.hasMore).toBe(true);
  });

  it("handles a missing results array as empty", async () => {
    captureSearch({ total: 0 });
    const res = await searchApi.search({ query: "zzz" });
    expect(res.data).toEqual([]);
    expect(res.total).toBe(0);
  });

  it("sends q and type, and omits type for 'all'", async () => {
    const seen = captureSearch({ results: [], total: 0 });
    await searchApi.search({ query: "hello world", type: "document" });
    await searchApi.search({ query: "x", type: "all" });
    expect(seen[0].searchParams.get("q")).toBe("hello world");
    expect(seen[0].searchParams.get("type")).toBe("document");
    expect(seen[1].searchParams.has("type")).toBe(false);
  });
});

describe("searchApi.suggest (QA)", () => {
  it("returns suggestions array", async () => {
    billingServer.use(
      http.get(`${SEARCH_URL}/suggest`, ({ request }) => {
        const q = new URL(request.url).searchParams.get("q");
        return HttpResponse.json({ suggestions: [`${q}-one`, `${q}-two`], query: q });
      })
    );
    expect(await searchApi.suggest("ot")).toEqual(["ot-one", "ot-two"]);
  });

  it("returns [] when suggestions key is missing", async () => {
    billingServer.use(http.get(`${SEARCH_URL}/suggest`, () => HttpResponse.json({})));
    expect(await searchApi.suggest("ot")).toEqual([]);
  });
});
