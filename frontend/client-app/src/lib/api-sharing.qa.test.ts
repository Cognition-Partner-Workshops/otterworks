import { http, HttpResponse } from "msw";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { filesApi } from "./api";
import { billingServer as server } from "../test-setup";

const API = "http://localhost:3000/api/v1";
const ME = "11111111-1111-4111-8111-111111111111";
const BOB = "22222222-2222-4222-8222-222222222222";
const FILE = "33333333-3333-4333-8333-333333333333";

function fakeJwt(sub: string): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
  return `${b64({ alg: "HS256" })}.${b64({ sub })}.sig`;
}

function rawFile(overrides: Record<string, unknown> = {}) {
  return {
    id: FILE,
    name: "Budget.xlsx",
    mime_type: "application/vnd.ms-excel",
    size_bytes: 10,
    s3_key: "k",
    folder_id: null,
    owner_id: ME,
    version: 1,
    is_trashed: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function rawShare(sharedWith: string, permission: string, id = crypto.randomUUID()) {
  return { id, file_id: FILE, shared_with: sharedWith, permission, shared_by: ME, created_at: "2026-01-01T00:00:00Z" };
}

describe("filesApi sharing (QA)", () => {
  beforeEach(() => localStorage.setItem("otter_access_token", fakeJwt(ME)));
  afterEach(() => localStorage.clear());

  it("share() looks up the user by email and posts viewer permission", async () => {
    let lookupEmail: string | null = null;
    let body: unknown;
    server.use(
      http.get(`${API}/auth/users/lookup`, ({ request }) => {
        lookupEmail = new URL(request.url).searchParams.get("email");
        return HttpResponse.json({ id: BOB, email: "bob@example.test", displayName: "Bob" });
      }),
      http.post(`${API}/files/${FILE}/share`, async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ share: rawShare(BOB, "viewer") }, { status: 201 });
      })
    );
    await filesApi.share(FILE, "bob@example.test", "view");
    expect(lookupEmail).toBe("bob@example.test");
    expect(body).toEqual({ shared_with: BOB, permission: "viewer", shared_by: ME });
  });

  it("share() maps edit to editor", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.get(`${API}/auth/users/lookup`, () => HttpResponse.json({ id: BOB, email: "b", displayName: "B" })),
      http.post(`${API}/files/${FILE}/share`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ share: rawShare(BOB, "editor") }, { status: 201 });
      })
    );
    await filesApi.share(FILE, "b", "edit");
    expect(body.permission).toBe("editor");
  });

  it("share() rejects when the email is not a registered user", async () => {
    server.use(
      http.get(`${API}/auth/users/lookup`, () => HttpResponse.json({ error: "not found" }, { status: 404 }))
    );
    await expect(filesApi.share(FILE, "ghost@example.test", "view")).rejects.toBeTruthy();
  });

  it("share() refuses to send when there is no logged-in user", async () => {
    localStorage.clear();
    server.use(
      http.get(`${API}/auth/users/lookup`, () => HttpResponse.json({ id: BOB, email: "b", displayName: "B" }))
    );
    await expect(filesApi.share(FILE, "b", "view")).rejects.toThrow("Unable to determine current user");
  });

  it("updateSharePermission() re-posts the share with the new role", async () => {
    let body: Record<string, unknown> = {};
    server.use(
      http.post(`${API}/files/${FILE}/share`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ share: rawShare(BOB, "editor") });
      })
    );
    await filesApi.updateSharePermission(FILE, BOB, "edit");
    expect(body).toEqual({ shared_with: BOB, permission: "editor", shared_by: ME });
  });

  it("removeShare() issues DELETE /files/:id/share/:userId", async () => {
    let called = false;
    server.use(
      http.delete(`${API}/files/${FILE}/share/${BOB}`, () => {
        called = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    await filesApi.removeShare(FILE, BOB);
    expect(called).toBe(true);
  });

  it("get() maps viewer/editor shares to view/edit and dedupes users", async () => {
    const CAROL = "44444444-4444-4444-8444-444444444444";
    server.use(
      http.get(`${API}/files/${FILE}`, () =>
        HttpResponse.json({
          ...rawFile(),
          shared_with: [rawShare(BOB, "viewer"), rawShare(BOB, "editor"), rawShare(CAROL, "editor")],
        })
      )
    );
    const file = await filesApi.get(FILE);
    expect(file.ownerId).toBe(ME);
    expect(file.sharedWith).toEqual([
      { userId: BOB, name: "", email: "", permission: "view" },
      { userId: CAROL, name: "", email: "", permission: "edit" },
    ]);
  });

  it("get() treats unknown permission strings as view", async () => {
    server.use(
      http.get(`${API}/files/${FILE}`, () =>
        HttpResponse.json({ ...rawFile(), shared_with: [rawShare(BOB, "admin")] })
      )
    );
    const file = await filesApi.get(FILE);
    expect(file.sharedWith[0].permission).toBe("view");
  });

  it("getShared() normalises the shared-with-me list and paging", async () => {
    let params: URLSearchParams | null = null;
    server.use(
      http.get(`${API}/files/shared`, ({ request }) => {
        params = new URL(request.url).searchParams;
        return HttpResponse.json({ files: [rawFile({ owner_id: BOB })], total: 1, page: 1, page_size: 50 });
      })
    );
    const res = await filesApi.getShared();
    expect(params!.get("page")).toBe("1");
    expect(params!.get("page_size")).toBe("50");
    expect(res.total).toBe(1);
    expect(res.hasMore).toBe(false);
    expect(res.data[0]).toMatchObject({ id: FILE, name: "Budget.xlsx", ownerId: BOB, isFolder: false });
  });

  it("getShared() reports hasMore when more pages exist", async () => {
    server.use(
      http.get(`${API}/files/shared`, () =>
        HttpResponse.json({ files: [rawFile()], total: 3, page: 1, page_size: 1 })
      )
    );
    const res = await filesApi.getShared(1, 1);
    expect(res.hasMore).toBe(true);
  });

  it("getShared() tolerates an empty payload", async () => {
    server.use(http.get(`${API}/files/shared`, () => HttpResponse.json({})));
    const res = await filesApi.getShared();
    expect(res.data).toEqual([]);
    expect(res.total).toBe(0);
  });
});
