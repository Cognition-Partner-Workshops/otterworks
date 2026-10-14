import { beforeEach, describe, expect, it, vi } from "vitest";

const { get, post, patch } = vi.hoisted(() => ({ get: vi.fn(), post: vi.fn(), patch: vi.fn() }));
vi.mock("@/lib/api-client", () => ({ apiClient: { get, post, patch }, API_BASE_URL: "/api/v1" }));

import { filesApi, starredApi } from "@/lib/api";
import { formatFileSize, getFileIcon } from "@/lib/utils";

const rawFile = {
  id: "f1",
  name: "report.pdf",
  mimeType: "application/pdf",
  sizeBytes: 2048,
  s3Key: "files/u/f1",
  folderId: "folder-1",
  ownerId: "u1",
  version: 3,
  isTrashed: false,
  createdAt: "2026-01-01T00:00:00Z",
  updatedAt: "2026-01-02T00:00:00Z",
};

function fakeJwt(sub: string): string {
  const b64 = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, "");
  return `${b64({ alg: "HS384" })}.${b64({ sub })}.sig`;
}

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
  localStorage.clear();
});

describe("formatFileSize", () => {
  it.each([
    [0, "0 B"],
    [1, "1 B"],
    [1023, "1023 B"],
    [1024, "1 KB"],
    [1536, "1.5 KB"],
    [1048576, "1 MB"],
    [104857600, "100 MB"],
    [1073741824, "1 GB"],
  ])("formats %d bytes as %s", (bytes, expected) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});

describe("getFileIcon", () => {
  it.each([
    ["image/png", "image"],
    ["video/mp4", "video"],
    ["audio/mpeg", "music"],
    ["application/pdf", "file-text"],
    ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "table"],
    ["application/vnd.ms-powerpoint", "presentation"],
    ["application/msword", "file-text"],
    ["application/zip", "archive"],
    ["application/octet-stream", "file"],
  ])("maps %s to %s", (mime, icon) => {
    expect(getFileIcon(mime)).toBe(icon);
  });
});

describe("filesApi", () => {
  it("get maps backend fields onto FileItem", async () => {
    get.mockResolvedValue({ data: rawFile });
    const file = await filesApi.get("f1");
    expect(get).toHaveBeenCalledWith("/files/f1");
    expect(file).toMatchObject({
      id: "f1",
      name: "report.pdf",
      mimeType: "application/pdf",
      size: 2048,
      parentId: "folder-1",
      ownerId: "u1",
      isFolder: false,
      isTrashed: false,
    });
  });

  it("get falls back to octet-stream and 0 bytes when fields are missing", async () => {
    get.mockResolvedValue({ data: { ...rawFile, mimeType: undefined, sizeBytes: undefined, folderId: undefined } });
    const file = await filesApi.get("f1");
    expect(file.mimeType).toBe("application/octet-stream");
    expect(file.size).toBe(0);
    expect(file.parentId).toBeNull();
  });

  it("list passes pagination + folder and computes hasMore", async () => {
    get.mockResolvedValue({ data: { files: [rawFile], total: 3, page: 1, pageSize: 2 } });
    const result = await filesApi.list("folder-1", 1, 2);
    expect(get).toHaveBeenCalledWith("/files", { params: { page: 1, page_size: 2, folder_id: "folder-1" } });
    expect(result.data).toHaveLength(1);
    expect(result.hasMore).toBe(true);
  });

  it("list omits folder_id at root and reports no more pages when exhausted", async () => {
    get.mockResolvedValue({ data: { files: [rawFile], total: 1, page: 1, pageSize: 50 } });
    const result = await filesApi.list(null);
    expect(get.mock.calls[0][1].params).not.toHaveProperty("folder_id");
    expect(result.hasMore).toBe(false);
  });

  it("upload sends multipart with file, folder and owner from JWT and reports progress", async () => {
    localStorage.setItem("otter_access_token", fakeJwt("owner-123"));
    post.mockResolvedValue({ data: { file: rawFile } });
    const onUploadProgress = vi.fn();
    const blob = new File(["hello"], "hello.txt", { type: "text/plain" });

    const file = await filesApi.upload(blob, "folder-1", { onUploadProgress });

    const [url, form, config] = post.mock.calls[0];
    expect(url).toBe("/files/upload");
    expect((form as FormData).get("file")).toBeInstanceOf(File);
    expect((form as FormData).get("folder_id")).toBe("folder-1");
    expect((form as FormData).get("owner_id")).toBe("owner-123");
    config.onUploadProgress({ loaded: 50, total: 200 });
    expect(onUploadProgress).toHaveBeenCalledWith(25);
    expect(file.id).toBe("f1");
  });

  it("upload omits folder_id at root and owner_id without a token", async () => {
    post.mockResolvedValue({ data: { file: rawFile } });
    await filesApi.upload(new File(["x"], "x.txt"), null);
    const form = post.mock.calls[0][1] as FormData;
    expect(form.has("folder_id")).toBe(false);
    expect(form.has("owner_id")).toBe(false);
  });

  it("getDownloadUrl rewrites the docker-internal localstack host", async () => {
    get.mockResolvedValue({ data: { url: "http://localstack:4566/bucket/key?sig=1", expiresInSecs: 3600 } });
    expect(await filesApi.getDownloadUrl("f1")).toBe("http://localhost:4566/bucket/key?sig=1");
    expect(get).toHaveBeenCalledWith("/files/f1/download");
  });

  it("getDownloadUrl leaves non-localstack URLs untouched", async () => {
    get.mockResolvedValue({ data: { url: "https://s3.amazonaws.com/b/k", expiresInSecs: 60 } });
    expect(await filesApi.getDownloadUrl("f1")).toBe("https://s3.amazonaws.com/b/k");
  });

  it("delete soft-deletes via the trash endpoint", async () => {
    post.mockResolvedValue({ data: {} });
    await filesApi.delete("f1");
    expect(post).toHaveBeenCalledWith("/files/f1/trash");
  });

  it("renameFile PATCHes the new name and maps the response", async () => {
    patch.mockResolvedValue({ data: { ...rawFile, name: "renamed.pdf" } });
    const file = await filesApi.renameFile("f1", "renamed.pdf");
    expect(patch).toHaveBeenCalledWith("/files/f1/rename", { name: "renamed.pdf" });
    expect(file.name).toBe("renamed.pdf");
  });
});

describe("starredApi", () => {
  it("toggle stars then unstars and persists to localStorage", () => {
    expect(starredApi.isStarred("u1", "f1")).toBe(false);
    expect(starredApi.toggle("u1", "f1", "file")).toBe(true);
    expect(starredApi.isStarred("u1", "f1")).toBe(true);
    expect(JSON.parse(localStorage.getItem("otter_starred_items")!)).toHaveProperty("u1:f1");
    expect(starredApi.toggle("u1", "f1", "file")).toBe(false);
    expect(starredApi.isStarred("u1", "f1")).toBe(false);
  });

  it("stars are scoped per user", () => {
    starredApi.toggle("u1", "f1", "file");
    expect(starredApi.isStarred("u2", "f1")).toBe(false);
    expect(starredApi.getStarredIds("u2").fileIds).toEqual([]);
    expect(starredApi.getStarredIds("u1").fileIds).toEqual(["f1"]);
  });

  it("getStarredIds groups by item type", () => {
    starredApi.toggle("u1", "f1", "file");
    starredApi.toggle("u1", "d1", "folder");
    const ids = starredApi.getStarredIds("u1");
    expect(ids.fileIds).toEqual(["f1"]);
    expect(ids.folderIds).toEqual(["d1"]);
  });

  it("survives corrupted storage", () => {
    localStorage.setItem("otter_starred_items", "{not json");
    expect(starredApi.isStarred("u1", "f1")).toBe(false);
    expect(starredApi.toggle("u1", "f1", "file")).toBe(true);
  });
});
