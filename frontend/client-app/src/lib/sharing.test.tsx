import { http, HttpResponse } from "msw";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { billingServer } from "../test-setup";
import { documentsApi, filesApi } from "./api";
import { ShareDialog } from "@/components/files/share-dialog";

const API = "http://localhost:3000/api/v1";
const OWNER_ID = "11111111-1111-4111-8111-111111111111";
const FRIEND_ID = "22222222-2222-4222-8222-222222222222";
const FILE_ID = "33333333-3333-4333-8333-333333333333";

function b64url(value: object): string {
  return btoa(JSON.stringify(value)).replace(/=+$/, "").replace(/\+/g, "-").replace(/\//g, "_");
}

function fakeJwt(sub: string): string {
  return [b64url({ alg: "none", typ: "JWT" }), b64url({ sub }), "sig"].join(".");
}

beforeEach(() => localStorage.setItem("otter_access_token", fakeJwt(OWNER_ID)));
afterEach(() => localStorage.clear());

describe("filesApi sharing", () => {
  it("share() resolves the email and posts viewer permission with the caller as sharer", async () => {
    let body: Record<string, unknown> | undefined;
    billingServer.use(
      http.get(`${API}/auth/users/lookup`, ({ request }) => {
        expect(new URL(request.url).searchParams.get("email")).toBe("friend@example.test");
        return HttpResponse.json({ id: FRIEND_ID, email: "friend@example.test", displayName: "Friend" });
      }),
      http.post(`${API}/files/${FILE_ID}/share`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ share: {} }, { status: 201 });
      })
    );
    await filesApi.share(FILE_ID, "friend@example.test", "view");
    expect(body).toEqual({ shared_with: FRIEND_ID, permission: "viewer", shared_by: OWNER_ID });
  });

  it("updateSharePermission() maps edit to editor", async () => {
    let body: Record<string, unknown> | undefined;
    billingServer.use(
      http.post(`${API}/files/${FILE_ID}/share`, async ({ request }) => {
        body = (await request.json()) as Record<string, unknown>;
        return HttpResponse.json({ share: {} });
      })
    );
    await filesApi.updateSharePermission(FILE_ID, FRIEND_ID, "edit");
    expect(body).toEqual({ shared_with: FRIEND_ID, permission: "editor", shared_by: OWNER_ID });
  });

  it("share() refuses to run without a signed-in user", async () => {
    localStorage.clear();
    billingServer.use(
      http.get(`${API}/auth/users/lookup`, () =>
        HttpResponse.json({ id: FRIEND_ID, email: "f@example.test", displayName: "F" })
      )
    );
    await expect(filesApi.share(FILE_ID, "f@example.test", "view")).rejects.toThrow(/current user/);
  });

  it("removeShare() deletes the recipient's share", async () => {
    let hit = false;
    billingServer.use(
      http.delete(`${API}/files/${FILE_ID}/share/${FRIEND_ID}`, () => {
        hit = true;
        return new HttpResponse(null, { status: 204 });
      })
    );
    await filesApi.removeShare(FILE_ID, FRIEND_ID);
    expect(hit).toBe(true);
  });

  it("getShared() normalises files and maps share permissions", async () => {
    billingServer.use(
      http.get(`${API}/files/shared`, () =>
        HttpResponse.json({
          files: [
            {
              id: FILE_ID,
              name: "plan.txt",
              mime_type: "text/plain",
              size_bytes: 5,
              s3_key: "k",
              folder_id: null,
              owner_id: OWNER_ID,
              version: 1,
              is_trashed: false,
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
              shared_with: [
                { id: "s1", file_id: FILE_ID, shared_with: FRIEND_ID, permission: "editor", shared_by: OWNER_ID, created_at: "" },
                { id: "s2", file_id: FILE_ID, shared_with: FRIEND_ID, permission: "viewer", shared_by: OWNER_ID, created_at: "" },
              ],
            },
          ],
          total: 1,
          page: 1,
          page_size: 50,
        })
      )
    );
    const result = await filesApi.getShared();
    expect(result.total).toBe(1);
    expect(result.data[0]).toMatchObject({ id: FILE_ID, name: "plan.txt", ownerId: OWNER_ID, size: 5 });
    expect(result.data[0].sharedWith).toEqual([
      { userId: FRIEND_ID, name: "", email: "", permission: "edit" },
    ]);
  });

  it("getTrashed() scopes the trash listing to the signed-in owner", async () => {
    let ownerParam: string | null = null;
    billingServer.use(
      http.get(`${API}/files/trash`, ({ request }) => {
        ownerParam = new URL(request.url).searchParams.get("owner_id");
        return HttpResponse.json({ files: [], total: 0, page: 1, page_size: 50 });
      })
    );
    await filesApi.getTrashed();
    expect(ownerParam).toBe(OWNER_ID);
  });
});

describe("documentsApi.share", () => {
  it.fails(
    "[REAL] invites a collaborator by email (client posts {users} to an endpoint that only mints a link token)",
    async () => {
      let body: unknown;
      billingServer.use(
        http.post(`${API}/documents/doc-1/share`, async ({ request }) => {
          body = await request.json();
          return HttpResponse.json({ document_id: "doc-1", token: "abcd" });
        })
      );
      await documentsApi.share("doc-1", [
        { userId: "", name: "", email: "friend@example.test", permission: "edit" },
      ]);
      // A real invite must resolve the recipient to a user id before sending it.
      expect(body).toMatchObject({ users: [{ userId: FRIEND_ID }] });
    }
  );
});

describe("ShareDialog", () => {
  const baseProps = {
    fileId: FILE_ID,
    fileName: "plan.txt",
    ownerId: OWNER_ID,
    ownerName: "Owner Otter",
    onClose: vi.fn(),
  };

  it("shares with the typed email at the chosen permission", async () => {
    const onShare = vi.fn().mockResolvedValue(undefined);
    render(<ShareDialog {...baseProps} sharedWith={[]} onShare={onShare} />);
    expect(screen.getAllByText("No one else has access yet").length).toBeGreaterThan(0);
    fireEvent.change(screen.getByPlaceholderText(/email/i), { target: { value: "friend@example.test" } });
    const permissionSelect = screen.getAllByRole("combobox")[0];
    fireEvent.change(permissionSelect, { target: { value: "edit" } });
    fireEvent.click(screen.getByRole("button", { name: /^share$/i }));
    await waitFor(() => expect(onShare).toHaveBeenCalledWith("friend@example.test", "edit"));
  });

  it("lists collaborators and supports permission change and removal", async () => {
    const onPermissionChange = vi.fn().mockResolvedValue(undefined);
    const onRemoveAccess = vi.fn().mockResolvedValue(undefined);
    render(
      <ShareDialog
        {...baseProps}
        sharedWith={[{ userId: FRIEND_ID, name: "", email: "", permission: "view" }]}
        resolvedUsers={{ [FRIEND_ID]: { name: "Friend Otter", email: "friend@example.test" } }}
        onShare={vi.fn()}
        onPermissionChange={onPermissionChange}
        onRemoveAccess={onRemoveAccess}
      />
    );
    expect(screen.getByText("Friend Otter")).toBeInTheDocument();
    expect(screen.getByText("Owner")).toBeInTheDocument();
    const rowSelect = screen.getAllByDisplayValue("Viewer").at(-1)!;
    fireEvent.change(rowSelect, { target: { value: "edit" } });
    await waitFor(() => expect(onPermissionChange).toHaveBeenCalledWith(FRIEND_ID, "edit"));
    fireEvent.click(screen.getByTitle("Remove access"));
    await waitFor(() => expect(onRemoveAccess).toHaveBeenCalledWith(FRIEND_ID));
  });

  it("link tab shows the file link and restricted access by default", () => {
    render(<ShareDialog {...baseProps} sharedWith={[]} onShare={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: /link/i }));
    expect(screen.getByText(`${window.location.origin}/files/${FILE_ID}`)).toBeInTheDocument();
    expect(screen.getByText("Only people with access can open this link")).toBeInTheDocument();
  });
});
