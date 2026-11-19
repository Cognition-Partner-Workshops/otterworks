import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  writeFile: vi.fn(),
  share: vi.fn(),
}));

vi.mock("@capacitor/core", () => ({
  Capacitor: { isNativePlatform: () => true },
  CapacitorHttp: { get: mocks.get },
}));
vi.mock("@capacitor/filesystem", () => ({
  Directory: { Documents: "DOCUMENTS" },
  Encoding: { UTF8: "utf8" },
  Filesystem: { writeFile: mocks.writeFile },
}));
vi.mock("@capacitor/share", () => ({ Share: { share: mocks.share } }));

import { safeFileName, saveTextToDevice, saveUrlToDevice, versionFileName } from "./native-files";

describe("native file saving", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.writeFile.mockResolvedValue({ uri: "file:///Documents/saved" });
    mocks.share.mockResolvedValue({});
  });

  it("downloads binary data natively and writes it to Documents before sharing", async () => {
    mocks.get.mockResolvedValue({ status: 200, data: "SGFyYm9y", headers: {}, url: "" });
    await expect(saveUrlToDevice("https://s3.example/presigned", "Harbor report.txt")).resolves.toBe("file:///Documents/saved");
    expect(mocks.get).toHaveBeenCalledWith({ url: "https://s3.example/presigned", responseType: "blob" });
    expect(mocks.writeFile).toHaveBeenCalledWith({ path: "Harbor report.txt", data: "SGFyYm9y", directory: "DOCUMENTS", encoding: undefined, recursive: true });
    expect(mocks.share).toHaveBeenCalledWith({ title: "Harbor report.txt", files: ["file:///Documents/saved"] });
  });

  it("rejects failed downloads without writing a file", async () => {
    mocks.get.mockResolvedValue({ status: 403, data: "", headers: {}, url: "" });
    await expect(saveUrlToDevice("https://s3.example/expired", "a.txt")).rejects.toThrow("HTTP 403");
    expect(mocks.writeFile).not.toHaveBeenCalled();
  });

  it("saves JSON files that the native HTTP layer already parsed", async () => {
    mocks.get.mockResolvedValue({ status: 200, data: { a: 1 }, headers: {}, url: "" });
    await saveUrlToDevice("https://s3.example/data.json", "data.json");
    expect(mocks.writeFile).toHaveBeenCalledWith(expect.objectContaining({ path: "data.json", data: '{\n  "a": 1\n}', encoding: "utf8" }));
  });

  it("writes CSV text as UTF-8 and keeps the file when the share sheet is dismissed", async () => {
    mocks.share.mockRejectedValue(new Error("Share canceled"));
    await expect(saveTextToDevice("sku\nHARBOR-01\n", "sku-margins-2026-11-01.csv")).resolves.toBe("file:///Documents/saved");
    expect(mocks.writeFile).toHaveBeenCalledWith(expect.objectContaining({ path: "sku-margins-2026-11-01.csv", data: "sku\nHARBOR-01\n", encoding: "utf8" }));
  });

  it("builds safe file names", () => {
    expect(safeFileName("../reports/q1:final.txt")).toBe("_reports_q1_final.txt");
    expect(safeFileName("  ")).toBe("download");
    expect(versionFileName("Harbor report.txt", 2)).toBe("Harbor report (v2).txt");
    expect(versionFileName("README", 3)).toBe("README (v3)");
  });
});
