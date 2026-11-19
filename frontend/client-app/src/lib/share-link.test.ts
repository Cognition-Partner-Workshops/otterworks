import { Clipboard } from "@capacitor/clipboard";
import { Capacitor } from "@capacitor/core";
import { afterEach, describe, expect, it, vi } from "vitest";
import { copyShareLink, getShareLink } from "./share-link";

vi.mock("@capacitor/clipboard", () => ({ Clipboard: { write: vi.fn() } }));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllEnvs();
  vi.unstubAllGlobals();
});

describe("getShareLink", () => {
  it("builds native file and document links from the configured web origin", () => {
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    vi.stubEnv("VITE_PUBLIC_WEB_ORIGIN", "https://app.example.com/");

    expect(getShareLink("files", "file-1")).toBe("https://app.example.com/files/file-1");
    expect(getShareLink("documents", "doc-1")).toBe("https://app.example.com/documents/doc-1");
  });

  it.each([
    undefined,
    "capacitor://localhost",
    "app.example.com",
    "https://example.com/api",
    "https://user:pass@example.com",
    "https://example.com/?name=value",
    "https://example.com/#fragment",
  ])("does not expose the WebView origin when the native origin is invalid (%s)", (origin) => {
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    vi.stubEnv("VITE_PUBLIC_WEB_ORIGIN", origin);

    expect(getShareLink("files", "file-1")).toBeNull();
  });

  it("keeps web links on the current origin and encodes the route parameter", () => {
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(false);
    vi.stubEnv("VITE_PUBLIC_WEB_ORIGIN", "https://app.example.com");

    expect(getShareLink("documents", "chapter #1")).toBe(`${window.location.origin}/documents/chapter%20%231`);
  });
});

describe("copyShareLink", () => {
  const url = "https://app.example.com/documents/doc-1";

  it("writes through the native bridge and propagates a rejected write", async () => {
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(true);
    const failure = new Error("Native clipboard write failed");
    const write = vi.mocked(Clipboard.write)
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(failure);

    await expect(copyShareLink(url)).resolves.toBeUndefined();
    expect(write).toHaveBeenCalledWith({ string: url });
    await expect(copyShareLink(url)).rejects.toBe(failure);
  });

  it("uses the browser clipboard and propagates a denied write", async () => {
    vi.spyOn(Capacitor, "isNativePlatform").mockReturnValue(false);
    const failure = new Error("Browser clipboard permission denied");
    const writeText = vi.fn().mockRejectedValue(failure);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    await expect(copyShareLink(url)).rejects.toBe(failure);
    expect(writeText).toHaveBeenCalledWith(url);
  });
});
