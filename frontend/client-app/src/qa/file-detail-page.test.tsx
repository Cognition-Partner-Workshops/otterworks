import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";

const { filesApi } = vi.hoisted(() => ({
  filesApi: { get: vi.fn(), getDownloadUrl: vi.fn(), delete: vi.fn(), share: vi.fn() },
}));
vi.mock("@/lib/api", () => ({ filesApi, authApi: { lookupUserById: vi.fn() } }));
vi.mock("@/components/layout/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <>{children}</> }));
vi.mock("@/components/files/share-dialog", () => ({ ShareDialog: () => null }));

import FileDetailPage from "@/pages/file-detail";

function fileOf(mimeType: string, name = "item") {
  return {
    id: "f1",
    name,
    mimeType,
    size: 4096,
    parentId: null,
    ownerId: "u1",
    ownerName: "",
    isFolder: false,
    isTrashed: false,
    path: `/${name}`,
    sharedWith: [],
    tags: [],
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    versions: [],
  };
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/files/f1"]}>
        <Routes>
          <Route path="/files/:id" element={<FileDetailPage />} />
          <Route path="/files" element={<p>files list</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  Object.values(filesApi).forEach((fn) => fn.mockReset());
  filesApi.getDownloadUrl.mockResolvedValue("http://localhost:4566/b/k");
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("hello\nworld")));
});

describe("File detail page", () => {
  it("shows name, size and type", async () => {
    filesApi.get.mockResolvedValue(fileOf("text/plain", "notes.txt"));
    renderPage();
    expect(await screen.findByRole("heading", { name: "notes.txt" })).toBeInTheDocument();
    expect(screen.getAllByText(/4 KB/).length).toBeGreaterThan(0);
  });

  it.each([
    ["text/plain", "notes.txt", async () => expect(await screen.findByText("world")).toBeInTheDocument()],
    ["application/json", "data.json", async () => expect(await screen.findByText("world")).toBeInTheDocument()],
    ["application/pdf", "doc.pdf", async () => expect(await screen.findByTitle("PDF preview")).toBeInTheDocument()],
    ["image/png", "pic.png", async () => expect(await screen.findByAltText("pic.png")).toBeInTheDocument()],
    [
      "application/zip",
      "bundle.zip",
      async () => expect(await screen.findByText("Preview not available for this file type")).toBeInTheDocument(),
    ],
  ])("previews %s appropriately", async (mime, name, assertPreview) => {
    filesApi.get.mockResolvedValue(fileOf(mime, name));
    renderPage();
    await screen.findByRole("heading", { name });
    await assertPreview();
  });

  it("video preview renders a video element", async () => {
    filesApi.get.mockResolvedValue(fileOf("video/mp4", "clip.mp4"));
    const { container } = renderPage();
    await screen.findByRole("heading", { name: "clip.mp4" });
    await waitFor(() => expect(container.querySelector("video")).toHaveAttribute("src", "http://localhost:4566/b/k"));
  });

  it("shows not-found state when the file cannot be loaded", async () => {
    filesApi.get.mockRejectedValue(new Error("404"));
    renderPage();
    expect(await screen.findByText("File not found")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Back to files" })).toHaveAttribute("href", "/files");
  });

  it("delete moves file to trash and navigates back to the list", async () => {
    filesApi.get.mockResolvedValue(fileOf("text/plain", "notes.txt"));
    filesApi.delete.mockResolvedValue(undefined);
    renderPage();
    await screen.findByRole("heading", { name: "notes.txt" });
    fireEvent.click(screen.getByRole("button", { name: /Delete/ }));
    await waitFor(() => expect(filesApi.delete).toHaveBeenCalledWith("f1"));
    expect(await screen.findByText("files list")).toBeInTheDocument();
  });

  it("download fetches a fresh URL for the file", async () => {
    filesApi.get.mockResolvedValue(fileOf("application/zip", "bundle.zip"));
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new Blob(["zip"]))));
    globalThis.URL.createObjectURL = vi.fn(() => "blob:x");
    globalThis.URL.revokeObjectURL = vi.fn();
    renderPage();
    await screen.findByRole("heading", { name: "bundle.zip" });
    filesApi.getDownloadUrl.mockClear();
    fireEvent.click(screen.getAllByRole("button", { name: /Download/ })[0]);
    await waitFor(() => expect(filesApi.getDownloadUrl).toHaveBeenCalledWith("f1"));
  });
});
