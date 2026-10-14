import { http, HttpResponse } from "msw";
import { afterEach, describe, expect, it } from "vitest";
import { filesApi } from "@/lib/api";
import { billingServer as server } from "../test-setup";

const API = "http://localhost:3000/api/v1";

function rawFile(over: Record<string, unknown> = {}) {
  return {
    id: "f1",
    name: "a.txt",
    mime_type: "text/plain",
    size_bytes: 10,
    folder_id: null,
    owner_id: "u1",
    is_trashed: false,
    created_at: "2026-10-01T00:00:00Z",
    updated_at: "2026-10-02T00:00:00Z",
    ...over,
  };
}

function jwtFor(sub: string) {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
  return `${b64({ alg: "none" })}.${b64({ sub })}.sig`;
}

describe("browsing filesApi", () => {
  afterEach(() => localStorage.clear());

  it("list() requests root with page params and maps snake_case files", async () => {
    let url: URL | null = null;
    server.use(
      http.get(`${API}/files`, ({ request }) => {
        url = new URL(request.url);
        return HttpResponse.json({ files: [rawFile()], total: 1, page: 1, page_size: 50 });
      })
    );
    const res = await filesApi.list();
    expect(url!.searchParams.get("page")).toBe("1");
    expect(url!.searchParams.get("page_size")).toBe("50");
    expect(url!.searchParams.has("folder_id")).toBe(false);
    expect(res.data[0]).toMatchObject({ id: "f1", name: "a.txt", size: 10, mimeType: "text/plain", parentId: null, isFolder: false });
    expect(res.hasMore).toBe(false);
  });

  it("list(folderId) scopes the request to the folder", async () => {
    let folderParam: string | null = null;
    server.use(
      http.get(`${API}/files`, ({ request }) => {
        folderParam = new URL(request.url).searchParams.get("folder_id");
        return HttpResponse.json({ files: [], total: 0, page: 1, page_size: 50 });
      })
    );
    await filesApi.list("folder-9");
    expect(folderParam).toBe("folder-9");
  });

  it("list() computes hasMore from page * pageSize < total", async () => {
    server.use(
      http.get(`${API}/files`, ({ request }) => {
        const p = Number(new URL(request.url).searchParams.get("page"));
        return HttpResponse.json({ files: [rawFile()], total: 3, page: p, page_size: 1 });
      })
    );
    expect((await filesApi.list(null, 1, 1)).hasMore).toBe(true);
    expect((await filesApi.list(null, 2, 1)).hasMore).toBe(true);
    expect((await filesApi.list(null, 3, 1)).hasMore).toBe(false);
  });

  it("listFolders() uses parent_id and marks results as folders", async () => {
    let parent: string | null = "unset";
    server.use(
      http.get(`${API}/folders`, ({ request }) => {
        parent = new URL(request.url).searchParams.get("parent_id");
        return HttpResponse.json({ folders: [{ id: "d1", name: "Docs", parent_id: "p1", owner_id: "u1" }] });
      })
    );
    const folders = await filesApi.listFolders("p1");
    expect(parent).toBe("p1");
    expect(folders[0]).toMatchObject({ id: "d1", name: "Docs", isFolder: true, parentId: "p1", path: "/Docs" });
  });

  it("listFolders() at root omits parent_id", async () => {
    let hasParent = true;
    server.use(
      http.get(`${API}/folders`, ({ request }) => {
        hasParent = new URL(request.url).searchParams.has("parent_id");
        return HttpResponse.json({ folders: [] });
      })
    );
    expect(await filesApi.listFolders()).toEqual([]);
    expect(hasParent).toBe(false);
  });

  it("getFolder() returns a folder item for breadcrumb labels", async () => {
    server.use(http.get(`${API}/folders/d1`, () => HttpResponse.json({ id: "d1", name: "Reports", parent_id: null })));
    expect(await filesApi.getFolder("d1")).toMatchObject({ id: "d1", name: "Reports", isFolder: true });
  });

  it("getTrashed() sends owner_id from the JWT sub claim", async () => {
    localStorage.setItem("otter_access_token", jwtFor("user-42"));
    let owner: string | null = null;
    server.use(
      http.get(`${API}/files/trash`, ({ request }) => {
        owner = new URL(request.url).searchParams.get("owner_id");
        return HttpResponse.json({ files: [rawFile({ is_trashed: true })], total: 1, page: 1, page_size: 50 });
      })
    );
    const res = await filesApi.getTrashed();
    expect(owner).toBe("user-42");
    expect(res.data[0].isTrashed).toBe(true);
    expect(res.total).toBe(1);
  });

  it("getTrashed() without a token omits owner_id", async () => {
    let hasOwner = true;
    server.use(
      http.get(`${API}/files/trash`, ({ request }) => {
        hasOwner = new URL(request.url).searchParams.has("owner_id");
        return HttpResponse.json({ files: [] });
      })
    );
    const res = await filesApi.getTrashed();
    expect(hasOwner).toBe(false);
    expect(res).toMatchObject({ data: [], total: 0, hasMore: false });
  });

  it("restore() POSTs to /files/:id/restore and delete() POSTs to /files/:id/trash", async () => {
    const calls: string[] = [];
    server.use(
      http.post(`${API}/files/:id/restore`, ({ params }) => {
        calls.push(`restore:${params.id}`);
        return HttpResponse.json({});
      }),
      http.post(`${API}/files/:id/trash`, ({ params }) => {
        calls.push(`trash:${params.id}`);
        return HttpResponse.json({});
      })
    );
    await filesApi.delete("f1");
    await filesApi.restore("f1");
    expect(calls).toEqual(["trash:f1", "restore:f1"]);
  });

  it("permanentDelete() issues DELETE /files/:id", async () => {
    let method = "";
    server.use(
      http.delete(`${API}/files/f1`, ({ request }) => {
        method = request.method;
        return new HttpResponse(null, { status: 204 });
      })
    );
    await filesApi.permanentDelete("f1");
    expect(method).toBe("DELETE");
  });

  it("getRecent(limit) requests the first page with page_size=limit", async () => {
    let size: string | null = null;
    server.use(
      http.get(`${API}/files`, ({ request }) => {
        size = new URL(request.url).searchParams.get("page_size");
        return HttpResponse.json({ files: [rawFile(), rawFile({ id: "f2" })], total: 2 });
      })
    );
    const files = await filesApi.getRecent(6);
    expect(size).toBe("6");
    expect(files.map((f) => f.id)).toEqual(["f1", "f2"]);
    expect(files[0].size).toBe(10);
  });
});
