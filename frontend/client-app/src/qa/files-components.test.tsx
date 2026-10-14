import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FileCard } from "@/components/files/file-card";
import { FileUploadDropzone } from "@/components/files/file-upload-dropzone";
import { ImageFilePreview, PdfFilePreview, TextFilePreview } from "@/components/files/file-preview";
import { useAuthStore } from "@/stores/auth-store";
import type { FileItem } from "@/types";

const baseFile = {
  id: "f1",
  name: "report.pdf",
  mimeType: "application/pdf",
  size: 2048,
  parentId: null,
  ownerId: "u1",
  ownerName: "",
  isFolder: false,
  isTrashed: false,
  path: "/report.pdf",
  sharedWith: [],
  tags: [],
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
  versions: [],
} as unknown as FileItem;

function renderCard(props: Partial<Parameters<typeof FileCard>[0]> = {}) {
  return render(
    <MemoryRouter>
      <FileCard file={baseFile} {...props} />
    </MemoryRouter>
  );
}

function openMenu(container: HTMLElement) {
  const buttons = Array.from(container.querySelectorAll("button"));
  const menuButton = buttons.find((b) => !b.getAttribute("aria-label"))!;
  fireEvent.click(menuButton);
}

function sizedFile(name: string, bytes: number, type = "application/octet-stream") {
  const f = new File(["x"], name, { type });
  Object.defineProperty(f, "size", { value: bytes });
  return f;
}

beforeEach(() => {
  localStorage.clear();
  useAuthStore.setState({ user: { id: "u1" } as never, isAuthenticated: true, isLoading: false });
});

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("FileCard", () => {
  it.each(["grid", "list"] as const)("%s view shows name, size and links to detail", (view) => {
    renderCard({ view });
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
    expect(screen.getAllByText(/2 KB/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link")).toHaveAttribute("href", "/files/f1");
  });

  it("star then unstar toggles label, persists and notifies", () => {
    const onStarToggle = vi.fn();
    renderCard({ onStarToggle });
    fireEvent.click(screen.getByRole("button", { name: "Star" }));
    expect(screen.getByRole("button", { name: "Unstar" })).toBeInTheDocument();
    expect(localStorage.getItem("otter_starred_items")).toContain("u1:f1");
    fireEvent.click(screen.getByRole("button", { name: "Unstar" }));
    expect(screen.getByRole("button", { name: "Star" })).toBeInTheDocument();
    expect(onStarToggle).toHaveBeenCalledTimes(2);
  });

  it("star state is restored from storage on mount", () => {
    localStorage.setItem(
      "otter_starred_items",
      JSON.stringify({ "u1:f1": { itemId: "f1", itemType: "file", starredAt: "" } })
    );
    renderCard();
    expect(screen.getByRole("button", { name: "Unstar" })).toBeInTheDocument();
  });

  it("star is a no-op when logged out", () => {
    useAuthStore.setState({ user: null, isAuthenticated: false });
    renderCard();
    fireEvent.click(screen.getByRole("button", { name: "Star" }));
    expect(screen.getByRole("button", { name: "Star" })).toBeInTheDocument();
    expect(localStorage.getItem("otter_starred_items")).toBeNull();
  });

  it("menu exposes rename, download, share and delete for files", () => {
    const { container } = renderCard();
    openMenu(container);
    for (const label of ["Rename", "Download", "Share", "Delete"]) {
      expect(screen.getByRole("button", { name: new RegExp(label) })).toBeInTheDocument();
    }
  });

  it("menu hides download for folders", () => {
    const { container } = render(
      <MemoryRouter>
        <FileCard file={{ ...baseFile, isFolder: true, name: "Docs" }} />
      </MemoryRouter>
    );
    openMenu(container);
    expect(screen.queryByRole("button", { name: /Download/ })).not.toBeInTheDocument();
  });

  it("download and delete call back with the file id", () => {
    const onDownload = vi.fn();
    const onDelete = vi.fn();
    const { container } = renderCard({ onDownload, onDelete });
    openMenu(container);
    fireEvent.click(screen.getByRole("button", { name: /Download/ }));
    expect(onDownload).toHaveBeenCalledWith("f1", "report.pdf");
    openMenu(container);
    fireEvent.click(screen.getByRole("button", { name: /Delete/ }));
    expect(onDelete).toHaveBeenCalledWith("f1");
  });

  it("rename submits trimmed name on Enter exactly once", () => {
    const onRename = vi.fn();
    const { container } = renderCard({ onRename });
    openMenu(container);
    fireEvent.click(screen.getByRole("button", { name: /Rename/ }));
    const input = screen.getByRole("textbox");
    fireEvent.change(input, { target: { value: "  final.pdf " } });
    fireEvent.keyDown(input, { key: "Enter" });
    fireEvent.blur(input);
    expect(onRename).toHaveBeenCalledTimes(1);
    expect(onRename).toHaveBeenCalledWith("f1", "final.pdf");
  });

  it("rename does nothing for unchanged, blank or escaped input", () => {
    const onRename = vi.fn();
    const { container } = renderCard({ onRename });
    for (const action of ["same", "blank", "escape"] as const) {
      openMenu(container);
      fireEvent.click(screen.getByRole("button", { name: /Rename/ }));
      const input = screen.getByRole("textbox");
      if (action === "blank") fireEvent.change(input, { target: { value: "   " } });
      if (action === "escape") {
        fireEvent.change(input, { target: { value: "other.pdf" } });
        fireEvent.keyDown(input, { key: "Escape" });
      } else {
        fireEvent.keyDown(input, { key: "Enter" });
      }
    }
    expect(onRename).not.toHaveBeenCalled();
    expect(screen.getByText("report.pdf")).toBeInTheDocument();
  });
});

describe("FileUploadDropzone", () => {
  function renderDropzone(uploadFile = vi.fn().mockResolvedValue(undefined)) {
    const onUploadComplete = vi.fn();
    const utils = render(<FileUploadDropzone uploadFile={uploadFile} onUploadComplete={onUploadComplete} />);
    const input = utils.container.querySelector('input[type="file"]') as HTMLInputElement;
    return { ...utils, input, uploadFile, onUploadComplete };
  }

  it("advertises the picker/drop affordance and 100MB limit", () => {
    renderDropzone();
    expect(screen.getByText(/Drag & drop files here, or click to browse/)).toBeInTheDocument();
    expect(screen.getByText(/up to 100MB per file/)).toBeInTheDocument();
  });

  it("picker upload of multiple files calls uploadFile for each and marks complete", async () => {
    const { input, uploadFile, onUploadComplete } = renderDropzone();
    expect(input.multiple).toBe(true);
    const a = new File(["a"], "a.txt", { type: "text/plain" });
    const b = new File(["b"], "b.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [a, b] } });
    await waitFor(() => expect(uploadFile).toHaveBeenCalledTimes(2));
    expect(uploadFile.mock.calls.map((c) => c[0].name)).toEqual(["a.txt", "b.png"]);
    await waitFor(() => expect(onUploadComplete).toHaveBeenCalledTimes(2));
    expect(await screen.findByText(/Upload complete/)).toBeInTheDocument();
  });

  it("drag-and-drop upload calls uploadFile", async () => {
    const { container, uploadFile } = renderDropzone();
    const root = container.querySelector('[role="presentation"]') as HTMLElement;
    const file = new File(["drop"], "dropped.txt", { type: "text/plain" });
    const dataTransfer = { files: [file], items: [{ kind: "file", type: file.type, getAsFile: () => file }], types: ["Files"] };
    fireEvent.dragEnter(root, { dataTransfer });
    fireEvent.drop(root, { dataTransfer });
    await waitFor(() => expect(uploadFile).toHaveBeenCalledTimes(1));
    expect(uploadFile.mock.calls[0][0].name).toBe("dropped.txt");
  });

  it("shows progress while uploading", async () => {
    let report: (p: number) => void = () => {};
    const uploadFile = vi.fn((_f: File, opts: { onProgress: (p: number) => void }) => {
      report = opts.onProgress;
      return new Promise<void>(() => {});
    });
    const { input } = renderDropzone(uploadFile);
    fireEvent.change(input, { target: { files: [new File(["x"], "slow.txt")] } });
    await waitFor(() => expect(uploadFile).toHaveBeenCalled());
    act(() => report(42));
    expect(await screen.findByText("42%")).toBeInTheDocument();
  });

  it("failed upload shows error and retry re-uploads", async () => {
    const uploadFile = vi.fn().mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(undefined);
    const { input } = renderDropzone(uploadFile);
    fireEvent.change(input, { target: { files: [new File(["x"], "flaky.txt")] } });
    expect(await screen.findByText("Upload failed")).toBeInTheDocument();
    fireEvent.click(screen.getByTitle("Retry upload"));
    await waitFor(() => expect(uploadFile).toHaveBeenCalledTimes(2));
    await waitFor(() => expect(screen.queryByText("Upload failed")).not.toBeInTheDocument());
  });

  it("cancel aborts the request and removes the row", async () => {
    let signal: AbortSignal | undefined;
    const uploadFile = vi.fn((_f: File, opts: { signal: AbortSignal }) => {
      signal = opts.signal;
      return new Promise<void>((_, reject) => opts.signal.addEventListener("abort", () => reject(new Error("aborted"))));
    });
    const { input } = renderDropzone(uploadFile);
    fireEvent.change(input, { target: { files: [new File(["x"], "cancel-me.txt")] } });
    fireEvent.click(await screen.findByTitle("Cancel upload"));
    expect(signal?.aborted).toBe(true);
    await waitFor(() => expect(screen.queryByText("cancel-me.txt")).not.toBeInTheDocument());
  });

  it("accepts any file type, as advertised", async () => {
    const { input, uploadFile } = renderDropzone();
    fireEvent.change(input, { target: { files: [new File(["MZ"], "tool.exe", { type: "application/x-msdownload" })] } });
    await waitFor(() => expect(uploadFile).toHaveBeenCalledTimes(1));
  });

  it("rejects files over the advertised 100MB limit before uploading", async () => {
    const { input, uploadFile } = renderDropzone();
    fireEvent.change(input, { target: { files: [sizedFile("huge.iso", 100 * 1024 * 1024 + 1)] } });
    await new Promise((r) => setTimeout(r, 50));
    expect(uploadFile).not.toHaveBeenCalled();
  });
});

describe("File previews", () => {
  it("text preview renders numbered lines from a ranged fetch", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("line one\nline two", { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);
    render(<TextFilePreview presignedUrl="http://localhost:4566/b/k" fileName="notes.txt" />);
    expect(await screen.findByText("line one")).toBeInTheDocument();
    expect(screen.getByText("2 lines")).toBeInTheDocument();
    expect(fetchMock.mock.calls[0][1].headers.Range).toBe("bytes=0-499999");
    expect(screen.queryByText(/File truncated/)).not.toBeInTheDocument();
  });

  it("text preview flags truncation on 206", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("partial", { status: 206 })));
    render(<TextFilePreview presignedUrl="http://x/y" fileName="big.log" />);
    expect(await screen.findByText(/File truncated/)).toBeInTheDocument();
  });

  it("text preview falls back to an iframe when fetch fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("CORS")));
    render(<TextFilePreview presignedUrl="http://x/y" fileName="notes.txt" />);
    expect(await screen.findByTitle("Preview of notes.txt")).toHaveAttribute("src", "http://x/y");
  });

  it("text preview without URL shows a message", async () => {
    render(<TextFilePreview fileName="notes.txt" />);
    expect(await screen.findByText("No download URL available")).toBeInTheDocument();
  });

  it("pdf preview embeds iframe and open-in-tab link", () => {
    render(<PdfFilePreview presignedUrl="http://x/doc.pdf" />);
    expect(screen.getByTitle("PDF preview")).toHaveAttribute("src", "http://x/doc.pdf");
    expect(screen.getByRole("link", { name: /open in a new tab/ })).toHaveAttribute("href", "http://x/doc.pdf");
  });

  it("pdf preview without URL shows unavailable", () => {
    render(<PdfFilePreview />);
    expect(screen.getByText("PDF preview not available")).toBeInTheDocument();
  });

  it("image preview renders and degrades on load error", () => {
    render(<ImageFilePreview presignedUrl="http://x/p.png" fileName="p.png" />);
    const img = screen.getByAltText("p.png");
    fireEvent.error(img);
    expect(screen.getByText("Image preview not available")).toBeInTheDocument();
  });
});
