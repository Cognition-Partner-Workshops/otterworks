import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatFileSize, formatRelativeTime, getFileIcon, truncate } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";

describe("browsing utils: formatFileSize", () => {
  it.each([
    [0, "0 B"],
    [512, "512 B"],
    [1024, "1 KB"],
    [1536, "1.5 KB"],
    [1024 * 1024, "1 MB"],
    [5 * 1024 * 1024 * 1024, "5 GB"],
  ])("formats %d bytes as %s", (bytes, expected) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});

describe("browsing utils: formatRelativeTime", () => {
  const now = new Date("2026-10-14T12:00:00Z");
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  });
  afterEach(() => vi.useRealTimers());

  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();

  it("returns 'just now' under a minute", () => {
    expect(formatRelativeTime(ago(30_000))).toBe("just now");
  });
  it("returns minutes", () => {
    expect(formatRelativeTime(ago(5 * 60_000))).toBe("5m ago");
  });
  it("returns hours", () => {
    expect(formatRelativeTime(ago(3 * 3_600_000))).toBe("3h ago");
  });
  it("returns days under a week", () => {
    expect(formatRelativeTime(ago(2 * 86_400_000))).toBe("2d ago");
  });
  it("falls back to a locale date after a week", () => {
    const d = ago(10 * 86_400_000);
    expect(formatRelativeTime(d)).toBe(new Date(d).toLocaleDateString());
  });
});

describe("browsing utils: getFileIcon / truncate", () => {
  it.each([
    ["image/png", "image"],
    ["video/mp4", "video"],
    ["audio/mpeg", "music"],
    ["application/pdf", "file-text"],
    ["application/vnd.ms-excel", "table"],
    ["application/vnd.openxmlformats-officedocument.presentationml.presentation", "presentation"],
    ["application/msword", "file-text"],
    ["application/zip", "archive"],
    ["text/plain", "file"],
  ])("maps %s to %s", (mime, icon) => {
    expect(getFileIcon(mime)).toBe(icon);
  });

  it("truncates long names with an ellipsis and keeps short ones", () => {
    expect(truncate("short.txt", 20)).toBe("short.txt");
    expect(truncate("a-very-long-file-name.txt", 10)).toBe("a-very-...");
    expect(truncate("a-very-long-file-name.txt", 10)).toHaveLength(10);
  });
});

describe("browsing ui-store: view and sort state", () => {
  beforeEach(() =>
    useUIStore.setState({ viewMode: "grid", sortConfig: { field: "updatedAt", direction: "desc" }, sidebarOpen: true })
  );

  it("defaults to grid view sorted by last modified desc", () => {
    const s = useUIStore.getState();
    expect(s.viewMode).toBe("grid");
    expect(s.sortConfig).toEqual({ field: "updatedAt", direction: "desc" });
  });

  it("updates view mode and sort config", () => {
    useUIStore.getState().setViewMode("list");
    useUIStore.getState().setSortConfig({ field: "name", direction: "asc" });
    expect(useUIStore.getState().viewMode).toBe("list");
    expect(useUIStore.getState().sortConfig).toEqual({ field: "name", direction: "asc" });
  });

  it("toggles the sidebar", () => {
    useUIStore.getState().toggleSidebar();
    expect(useUIStore.getState().sidebarOpen).toBe(false);
    useUIStore.getState().setSidebarOpen(true);
    expect(useUIStore.getState().sidebarOpen).toBe(true);
  });
});
