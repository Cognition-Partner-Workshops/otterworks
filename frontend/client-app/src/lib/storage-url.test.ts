import { afterEach, describe, expect, it, vi } from "vitest";
import { rewriteStorageUrl } from "./storage-url";

afterEach(() => vi.unstubAllEnvs());

describe("rewriteStorageUrl", () => {
  const url = "http://localstack:4566/bucket/preview.png?X-Amz-Signature=a%2Fb&x=1#image";

  it("keeps the default web localhost rewrite when unset or empty", () => {
    for (const value of [undefined, ""]) {
      vi.stubEnv("VITE_STORAGE_PUBLIC_URL", value);
      expect(rewriteStorageUrl(url)).toBe(url.replace("localstack", "localhost"));
    }
  });

  it("uses the configured origin and preserves path and signed query bytes", () => {
    vi.stubEnv("VITE_STORAGE_PUBLIC_URL", "https://192.168.1.10:9443/ignored");
    expect(rewriteStorageUrl(url)).toBe(url.replace("http://localstack:4566", "https://192.168.1.10:9443"));
    expect(rewriteStorageUrl("http://localstack/bucket", "http://device:4010")).toBe("http://device:4010/bucket");
    expect(rewriteStorageUrl("http://LOCALSTACK:4566/bucket", "http://device:4010")).toBe("http://device:4010/bucket");
  });

  it("leaves real S3 and lookalike hosts untouched", () => {
    for (const source of ["https://bucket.s3.amazonaws.com/localstack:4566/key", "http://localstack.example:4566/key"]) {
      expect(rewriteStorageUrl(source, "http://device:4010")).toBe(source);
    }
  });

  it("safely leaves malformed URLs or invalid configuration unchanged", () => {
    for (const source of ["", "not a URL", "http://["]) expect(rewriteStorageUrl(source)).toBe(source);
    for (const target of ["not a URL", "file:///tmp/storage"]) expect(rewriteStorageUrl(url, target)).toBe(url);
  });
});
