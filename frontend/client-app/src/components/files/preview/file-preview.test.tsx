import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { FileItem } from "@/types";
import { FilePreview } from "./file-preview";

const previewUrl = vi.fn();
vi.mock("@/hooks/use-preview-url", () => ({
  usePreviewUrl: () => previewUrl(),
}));

const file: FileItem = {
  id: "preview-file",
  name: "notes.txt",
  mimeType: "text/plain",
  size: 12,
  parentId: null,
  ownerId: "owner",
  ownerName: "",
  isFolder: false,
  path: "/notes.txt",
  sharedWith: [],
  tags: [],
  createdAt: "2024-01-01T00:00:00Z",
  updatedAt: "2024-01-01T00:00:00Z",
  versions: [],
};

function renderPreview(item: FileItem, initialUrl = "http://storage/file") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  previewUrl.mockReturnValue({
    url: initialUrl,
    isLoading: false,
    notFound: false,
    error: null,
    refresh: vi.fn().mockResolvedValue(initialUrl),
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <FilePreview file={item} onDownload={vi.fn()} />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("FilePreview dispatcher (AC-16, AC-21, AC-23, AC-24, AC-29, AC-30)", () => {
  beforeEach(() => {
    previewUrl.mockReset();
  });

  it("shows the empty-file state without requesting a URL (AC-24)", () => {
    renderPreview({ ...file, size: 0 });
    expect(screen.getByText("This file is empty")).toBeInTheDocument();
    expect(previewUrl).not.toHaveBeenCalled();
  });

  it("gates large image previews until Load preview is clicked (AC-23)", async () => {
    const refresh = vi.fn().mockResolvedValue("http://storage/refreshed");
    previewUrl.mockReturnValue({
      url: "http://storage/file",
      isLoading: false,
      notFound: false,
      error: null,
      refresh,
    });
    render(<MemoryRouter><FilePreview file={{ ...file, mimeType: "image/png", size: 104_857_601 }} onDownload={vi.fn()} /></MemoryRouter>);
    expect(screen.getByText(/Large file \(/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Load preview" })).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Load preview" }));
    await waitFor(() => expect(refresh).toHaveBeenCalledTimes(1));
  });

  it("does not gate text or ZIP previews above the image/document threshold (AC-23)", () => {
    const { rerender } = renderPreview({ ...file, size: 104_857_601 });
    expect(screen.queryByRole("button", { name: "Load preview" })).not.toBeInTheDocument();
    rerender(<MemoryRouter><FilePreview file={{ ...file, mimeType: "application/zip", name: "archive.zip", size: 104_857_601 }} onDownload={vi.fn()} /></MemoryRouter>);
    expect(screen.queryByRole("button", { name: "Load preview" })).not.toBeInTheDocument();
  });

  it("shows the unsupported fallback with a Download action (AC-16)", () => {
    const onDownload = vi.fn();
    render(<MemoryRouter><FilePreview file={{ ...file, name: "README", mimeType: "application/octet-stream" }} onDownload={onDownload} /></MemoryRouter>);
    expect(screen.getByText("Preview isn't available for this file type")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Download" }));
    expect(onDownload).toHaveBeenCalledOnce();
  });

  it("shows not-found when the download URL is gone (AC-30)", () => {
    previewUrl.mockReturnValue({ url: undefined, isLoading: false, notFound: true, error: null, refresh: vi.fn() });
    render(<MemoryRouter><FilePreview file={file} onDownload={vi.fn()} /></MemoryRouter>);
    expect(screen.getByText("This file is no longer available")).toBeInTheDocument();
  });

  it("renders a loading state while the URL is loading (AC-21)", () => {
    previewUrl.mockReturnValue({ url: undefined, isLoading: true, notFound: false, error: null, refresh: vi.fn() });
    render(<MemoryRouter><FilePreview file={file} onDownload={vi.fn()} /></MemoryRouter>);
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
