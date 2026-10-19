import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

const apiMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock("./api-client", () => ({ apiClient: apiMock }));

import { filesApi } from "./api";

function base64Url(value: object): string {
  return btoa(JSON.stringify(value)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

function fakeToken(sub: string): string {
  return [base64Url({ alg: "none", typ: "JWT" }), base64Url({ sub }), "sig"].join(".");
}

const ownerId = "11111111-2222-3333-4444-555555555555";

const rawFile = {
  id: "f-1",
  name: "notes.txt",
  mimeType: "text/plain",
  sizeBytes: 42,
  s3Key: "owner/f-1/notes.txt",
  folderId: "folder-1",
  ownerId,
  version: 1,
  isTrashed: false,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  Object.values(apiMock).forEach((fn) => fn.mockReset());
  localStorage.setItem("otter_access_token", fakeToken(ownerId));
});

afterEach(() => {
  localStorage.clear();
});

describe("filesApi.list", () => {
  it("sends folder_id only when a parent folder is given", async () => {
    apiMock.get.mockResolvedValue({ data: { files: [], total: 0, page: 1, pageSize: 50 } });

    await filesApi.list();
    expect(apiMock.get).toHaveBeenLastCalledWith("/files", { params: { page: 1, page_size: 50 } });

    await filesApi.list("folder-1", 2, 10);
    expect(apiMock.get).toHaveBeenLastCalledWith("/files", {
      params: { page: 2, page_size: 10, folder_id: "folder-1" },
    });
  });

  it("maps raw file-service fields to FileItem and computes hasMore", async () => {
    apiMock.get.mockResolvedValue({ data: { files: [rawFile], total: 3, page: 1, pageSize: 2 } });

    const result = await filesApi.list(null, 1, 2);

    expect(result.total).toBe(3);
    expect(result.hasMore).toBe(true);
    expect(result.data[0]).toMatchObject({
      id: "f-1",
      name: "notes.txt",
      size: 42,
      parentId: "folder-1",
      ownerId,
      isFolder: false,
      isTrashed: false,
    });
  });

  it("reports no more pages on the last page", async () => {
    apiMock.get.mockResolvedValue({ data: { files: [rawFile], total: 1, page: 1, pageSize: 50 } });
    expect((await filesApi.list()).hasMore).toBe(false);
  });
});

describe("filesApi.upload", () => {
  it("posts multipart form data with the folder and the JWT subject as owner", async () => {
    apiMock.post.mockResolvedValue({ data: { file: rawFile } });
    const file = new File(["hello"], "notes.txt", { type: "text/plain" });

    const item = await filesApi.upload(file, "folder-1");

    const [url, body] = apiMock.post.mock.calls[0];
    expect(url).toBe("/files/upload");
    const form = body as FormData;
    expect((form.get("file") as File).name).toBe("notes.txt");
    expect(form.get("folder_id")).toBe("folder-1");
    expect(form.get("owner_id")).toBe(ownerId);
    expect(item.name).toBe("notes.txt");
  });

  it("omits folder_id for root uploads", async () => {
    apiMock.post.mockResolvedValue({ data: { file: rawFile } });
    await filesApi.upload(new File(["x"], "root.txt"));
    const form = apiMock.post.mock.calls[0][1] as FormData;
    expect(form.has("folder_id")).toBe(false);
  });

  it("reports upload progress as a percentage", async () => {
    apiMock.post.mockImplementation(async (_url, _body, config) => {
      config.onUploadProgress({ loaded: 25, total: 100 });
      return { data: { file: rawFile } };
    });
    const onUploadProgress = vi.fn();
    await filesApi.upload(new File(["x"], "p.txt"), null, { onUploadProgress });
    expect(onUploadProgress).toHaveBeenCalledWith(25);
  });
});

describe("filesApi.getDownloadUrl", () => {
  it("rewrites the internal LocalStack host to localhost", async () => {
    apiMock.get.mockResolvedValue({
      data: { url: "http://localstack:4566/otterworks-files/a/b.txt?X-Amz-Signature=abc", expiresInSecs: 3600 },
    });
    const url = await filesApi.getDownloadUrl("f-1");
    expect(apiMock.get).toHaveBeenCalledWith("/files/f-1/download");
    expect(url).toBe("http://localhost:4566/otterworks-files/a/b.txt?X-Amz-Signature=abc");
  });

  it("leaves real S3 URLs untouched", async () => {
    const s3 = "https://bucket.s3.amazonaws.com/a/b.txt?X-Amz-Signature=abc";
    apiMock.get.mockResolvedValue({ data: { url: s3, expiresInSecs: 3600 } });
    expect(await filesApi.getDownloadUrl("f-1")).toBe(s3);
  });
});

describe("filesApi mutations hit the expected routes", () => {
  it("rename, trash, restore and permanent delete", async () => {
    apiMock.patch.mockResolvedValue({ data: { ...rawFile, name: "renamed.txt" } });
    apiMock.post.mockResolvedValue({ data: {} });
    apiMock.delete.mockResolvedValue({ data: {} });

    const renamed = await filesApi.renameFile("f-1", "renamed.txt");
    await filesApi.delete("f-1");
    await filesApi.restore("f-1");
    await filesApi.permanentDelete("f-1");

    expect(renamed.name).toBe("renamed.txt");
    expect(apiMock.patch).toHaveBeenCalledWith("/files/f-1/rename", { name: "renamed.txt" });
    expect(apiMock.post).toHaveBeenCalledWith("/files/f-1/trash");
    expect(apiMock.post).toHaveBeenCalledWith("/files/f-1/restore");
    expect(apiMock.delete).toHaveBeenCalledWith("/files/f-1");
  });

  it("folder create, rename and delete", async () => {
    apiMock.post.mockResolvedValue({ data: { id: "folder-2", name: "Docs" } });
    apiMock.put.mockResolvedValue({ data: { id: "folder-2", name: "Docs v2" } });
    apiMock.delete.mockResolvedValue({ data: {} });

    await filesApi.createFolder("Docs", "folder-1");
    const renamed = await filesApi.renameFolder("folder-2", "Docs v2");
    await filesApi.deleteFolder("folder-2");

    expect(apiMock.post).toHaveBeenCalledWith("/folders", {
      name: "Docs",
      parent_id: "folder-1",
      owner_id: ownerId,
    });
    expect(renamed.isFolder).toBe(true);
    expect(apiMock.put).toHaveBeenCalledWith("/folders/folder-2", { name: "Docs v2" });
    expect(apiMock.delete).toHaveBeenCalledWith("/folders/folder-2");
  });

  it("listFolders maps folders and scopes by parent", async () => {
    apiMock.get.mockResolvedValue({ data: { folders: [{ id: "folder-2", name: "Docs", parentId: "folder-1" }] } });
    const folders = await filesApi.listFolders("folder-1");
    expect(apiMock.get).toHaveBeenCalledWith("/folders", { params: { parent_id: "folder-1" } });
    expect(folders[0]).toMatchObject({ id: "folder-2", name: "Docs", parentId: "folder-1", isFolder: true });
  });

  it("getTrashed scopes the trash listing to the JWT subject", async () => {
    apiMock.get.mockResolvedValue({ data: { files: [{ ...rawFile, isTrashed: true }], total: 1 } });
    const trash = await filesApi.getTrashed();
    expect(apiMock.get).toHaveBeenCalledWith("/files/trash", {
      params: { page: 1, page_size: 50, owner_id: ownerId },
    });
    expect(trash.data[0].isTrashed).toBe(true);
  });
});
