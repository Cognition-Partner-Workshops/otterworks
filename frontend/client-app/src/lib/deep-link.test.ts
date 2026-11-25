import { describe, expect, it } from "vitest";
import { getDeepLinkPath, isResourcePath } from "./deep-link";

const origin = "https://app.example.com";

describe("getDeepLinkPath", () => {
  it.each([
    ["otterworks://files/file-1", "/files/file-1"],
    ["otterworks://documents/doc-1", "/documents/doc-1"],
    [`${origin}/files/file-1`, "/files/file-1"],
    [`${origin}/documents/doc-1?from=share#content`, "/documents/doc-1"],
  ])("routes %s to %s", (url, path) => {
    expect(getDeepLinkPath(url, origin)).toBe(path);
  });

  it.each([
    "not a URL",
    "/files/file-1",
    "http://app.example.com/files/file-1",
    "https://app.example.com:444/files/file-1",
    "https://app.example.com.evil.test/files/file-1",
    "https://user@app.example.com/files/file-1",
    "other://files/file-1",
    "otterworks://unknown/file-1",
    "otterworks://files:99/file-1",
    "otterworks://files/",
    `${origin}/login`,
    `${origin}/files/file-1/download`,
    `${origin}/files/%2Fdownload`,
    `${origin}/unknown/../files/file-1`,
  ])("ignores %s", (url) => {
    expect(getDeepLinkPath(url, origin)).toBeNull();
  });

  it("only accepts a custom-scheme link when the public origin is unavailable", () => {
    expect(getDeepLinkPath(`${origin}/files/file-1`, null)).toBeNull();
    expect(getDeepLinkPath("otterworks://files/file-1", null)).toBe("/files/file-1");
  });
});

describe("isResourcePath", () => {
  it("only accepts an internal resource route as a login destination", () => {
    expect(isResourcePath("/documents/doc-1")).toBe(true);
    expect(isResourcePath("//app.example.com/documents/doc-1")).toBe(false);
    expect(isResourcePath(undefined)).toBe(false);
  });
});
