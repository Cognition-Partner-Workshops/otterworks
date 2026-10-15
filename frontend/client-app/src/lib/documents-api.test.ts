import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { apiClient } from "./api-client";
import { documentsApi } from "./api";

// QA pyramid (docs area): contract between documentsApi and document-service.
describe("documentsApi", () => {
  let getSpy: ReturnType<typeof vi.spyOn>;
  let postSpy: ReturnType<typeof vi.spyOn>;
  let patchSpy: ReturnType<typeof vi.spyOn>;
  let deleteSpy: ReturnType<typeof vi.spyOn>;

  beforeEach(() => {
    getSpy = vi.spyOn(apiClient, "get").mockResolvedValue({ data: { items: [], total: 0 } });
    postSpy = vi.spyOn(apiClient, "post").mockResolvedValue({ data: { id: "doc-1", title: "Untitled document" } });
    patchSpy = vi.spyOn(apiClient, "patch").mockResolvedValue({ data: { id: "doc-1" } });
    deleteSpy = vi.spyOn(apiClient, "delete").mockResolvedValue({ data: undefined });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("list() calls /documents with the page number", async () => {
    await documentsApi.list(2);
    expect(getSpy).toHaveBeenCalledWith("/documents", expect.objectContaining({ params: expect.objectContaining({ page: 2 }) }));
  });

  it("get() fetches a single document by id", async () => {
    await documentsApi.get("doc-1");
    expect(getSpy).toHaveBeenCalledWith("/documents/doc-1");
  });

  it("create() posts the title and returns the created document", async () => {
    const doc = await documentsApi.create("Untitled document");
    expect(postSpy).toHaveBeenCalledWith("/documents", { title: "Untitled document", parentId: undefined });
    expect(doc.id).toBe("doc-1");
  });

  it("update() sends a PATCH with only the changed fields", async () => {
    await documentsApi.update("doc-1", { content: "<p>hello</p>" });
    expect(patchSpy).toHaveBeenCalledWith("/documents/doc-1", { content: "<p>hello</p>" });
  });

  it("delete() issues DELETE /documents/:id", async () => {
    await documentsApi.delete("doc-1");
    expect(deleteSpy).toHaveBeenCalledWith("/documents/doc-1");
  });

  it("getRecent() uses the service's size param and unwraps items", async () => {
    getSpy.mockResolvedValueOnce({ data: { items: [{ id: "a" }, { id: "b" }] } });
    const items = await documentsApi.getRecent(6);
    expect(getSpy).toHaveBeenCalledWith("/documents", { params: { page: 1, size: 6 } });
    expect(items).toHaveLength(2);
  });

  // [REAL] document-service reads `size`; list() sends `pageSize`, so the
  // documents page is silently capped at the service default of 20 items.
  it.fails("[REAL] list() sends the page size as `size` (service ignores pageSize)", async () => {
    await documentsApi.list(1, 50);
    expect(getSpy).toHaveBeenCalledWith("/documents", { params: { page: 1, size: 50 } });
  });

  // [REAL] document-service has no POST /documents/:id/restore route (only
  // /documents/:id/versions/:versionId/restore), so restore() always 404s.
  it.fails("[REAL] restore() targets a route document-service exposes", async () => {
    await documentsApi.restore("doc-1");
    expect(postSpy).toHaveBeenCalledWith(expect.stringMatching(/^\/documents\/doc-1\/versions\/[^/]+\/restore$/));
  });
});
