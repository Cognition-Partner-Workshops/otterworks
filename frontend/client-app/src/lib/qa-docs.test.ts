import { afterEach, describe, expect, it, vi } from "vitest";
import { http, HttpResponse } from "msw";
import { billingServer } from "../test-setup";
import { documentsApi } from "./api";
import { formatRelativeTime, generateColor, getInitials, truncate } from "./utils";

const DOCS_URL = "http://localhost:3000/api/v1/documents";

const apiDoc = {
  id: "doc-1",
  title: "QA Doc",
  content: "<p>hello</p>",
  owner_id: "user-1",
  word_count: 1,
  updated_at: "2026-01-01T00:00:00Z",
  created_at: "2026-01-01T00:00:00Z",
  is_deleted: false,
};

function captureRequests() {
  const requests: Request[] = [];
  billingServer.events.on("request:start", ({ request }) => {
    requests.push(request.clone());
  });
  return requests;
}

afterEach(() => {
  billingServer.events.removeAllListeners();
  vi.useRealTimers();
});

describe("documentsApi (docs QA)", () => {
  it("list sends the backend's `size` page-size parameter", async () => {
    const requests = captureRequests();
    billingServer.use(
      http.get(DOCS_URL, () =>
        HttpResponse.json({ items: [apiDoc], total: 1, page: 1, size: 50, pages: 1 })
      )
    );

    await documentsApi.list(1, 50);

    const url = new URL(requests[0].url);
    expect(url.searchParams.get("page")).toBe("1");
    expect(url.searchParams.get("size")).toBe("50");
  });

  it("list converts snake_case document fields to camelCase", async () => {
    billingServer.use(
      http.get(DOCS_URL, () =>
        HttpResponse.json({ items: [apiDoc], total: 1, page: 1, size: 50, pages: 1 })
      )
    );

    const result = await documentsApi.list();
    const items = (result as unknown as { items: Record<string, unknown>[] }).items;
    const item = items[0];

    expect(item.ownerId).toBe("user-1");
    expect(item.updatedAt).toBe("2026-01-01T00:00:00Z");
    expect(item.wordCount).toBe(1);
    expect(item).not.toHaveProperty("owner_id");
  });

  it("getRecent requests a single page sized to the limit", async () => {
    const requests = captureRequests();
    billingServer.use(
      http.get(DOCS_URL, () => HttpResponse.json({ items: [apiDoc, apiDoc] }))
    );

    const recent = await documentsApi.getRecent(2);

    const url = new URL(requests[0].url);
    expect(url.searchParams.get("size")).toBe("2");
    expect(recent).toHaveLength(2);
  });

  it("getRecent tolerates a response without items", async () => {
    billingServer.use(http.get(DOCS_URL, () => HttpResponse.json({})));
    expect(await documentsApi.getRecent()).toEqual([]);
  });

  it("get fetches a single document by id", async () => {
    billingServer.use(http.get(`${DOCS_URL}/doc-1`, () => HttpResponse.json(apiDoc)));
    const doc = await documentsApi.get("doc-1");
    expect(doc.id).toBe("doc-1");
    expect(doc.content).toBe("<p>hello</p>");
  });

  it("create POSTs the title", async () => {
    let body: Record<string, unknown> | null = null;
    billingServer.use(
      http.post(DOCS_URL, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json(apiDoc, { status: 201 });
      })
    );

    const doc = await documentsApi.create("Untitled document");

    expect(body).toMatchObject({ title: "Untitled document" });
    expect(doc.id).toBe("doc-1");
  });

  it("update (autosave/rename) PATCHes only the changed fields", async () => {
    let method = "";
    let body: Record<string, unknown> | null = null;
    billingServer.use(
      http.patch(`${DOCS_URL}/doc-1`, async ({ request }) => {
        method = request.method;
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...apiDoc, title: "Renamed" });
      })
    );

    const doc = await documentsApi.update("doc-1", { title: "Renamed" });

    expect(method).toBe("PATCH");
    expect(body).toEqual({ title: "Renamed" });
    expect(doc.title).toBe("Renamed");
  });

  it("update sends rich-text HTML content verbatim", async () => {
    const html = "<h1>H</h1><p><strong>b</strong> <em>i</em></p>";
    let body: Record<string, unknown> | null = null;
    billingServer.use(
      http.patch(`${DOCS_URL}/doc-1`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ ...apiDoc, content: html });
      })
    );

    await documentsApi.update("doc-1", { content: html });

    expect(body).toEqual({ content: html });
  });

  it("delete issues DELETE /documents/:id", async () => {
    let called = false;
    billingServer.use(
      http.delete(`${DOCS_URL}/doc-1`, () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      })
    );

    await documentsApi.delete("doc-1");

    expect(called).toBe(true);
  });

  it("delete surfaces server errors to the caller", async () => {
    billingServer.use(
      http.delete(`${DOCS_URL}/doc-1`, () =>
        HttpResponse.json({ detail: "Forbidden" }, { status: 403 })
      )
    );

    await expect(documentsApi.delete("doc-1")).rejects.toMatchObject({
      response: { status: 403 },
    });
  });

  it("attaches the stored bearer token to document requests", async () => {
    localStorage.setItem("otter_access_token", "qa-token");
    let auth: string | null = null;
    billingServer.use(
      http.get(`${DOCS_URL}/doc-1`, ({ request }) => {
        auth = request.headers.get("authorization");
        return HttpResponse.json(apiDoc);
      })
    );

    await documentsApi.get("doc-1");
    localStorage.removeItem("otter_access_token");

    expect(auth).toBe("Bearer qa-token");
  });
});

describe("document card helpers (docs QA)", () => {
  it("formats relative edit times", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-10T12:00:00Z"));

    expect(formatRelativeTime("2026-01-10T11:59:30Z")).toBe("just now");
    expect(formatRelativeTime("2026-01-10T11:55:00Z")).toBe("5m ago");
    expect(formatRelativeTime("2026-01-10T09:00:00Z")).toBe("3h ago");
    expect(formatRelativeTime("2026-01-08T12:00:00Z")).toBe("2d ago");
  });

  it("falls back to a date for edits older than a week", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date("2026-01-30T12:00:00Z"));
    const old = "2026-01-01T12:00:00Z";
    expect(formatRelativeTime(old)).toBe(new Date(old).toLocaleDateString());
  });

  it("truncates long titles with an ellipsis", () => {
    expect(truncate("short", 10)).toBe("short");
    expect(truncate("a very long document title", 10)).toBe("a very ...");
    expect(truncate("a very long document title", 10)).toHaveLength(10);
  });

  it("derives owner initials", () => {
    expect(getInitials("ada lovelace")).toBe("AL");
    expect(getInitials("Single")).toBe("S");
    expect(getInitials("one two three")).toBe("OT");
  });

  it("generates a stable avatar colour per user", () => {
    expect(generateColor("user-1")).toBe(generateColor("user-1"));
    expect(generateColor("user-1")).toMatch(/^#[0-9a-f]{6}$/);
  });
});
