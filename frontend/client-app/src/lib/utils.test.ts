import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { formatFileSize, formatRelativeTime, getInitials, truncate, cn } from "./utils";

describe("formatRelativeTime", () => {
  const now = new Date("2026-06-15T12:00:00Z");
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(now);
  });
  afterEach(() => vi.useRealTimers());

  const ago = (ms: number) => new Date(now.getTime() - ms).toISOString();

  it.each([
    [10 * 1000, "just now"],
    [5 * 60 * 1000, "5m ago"],
    [3 * 60 * 60 * 1000, "3h ago"],
    [2 * 24 * 60 * 60 * 1000, "2d ago"],
  ])("formats %d ms ago as %s", (ms, expected) => {
    expect(formatRelativeTime(ago(ms))).toBe(expected);
  });

  it("falls back to a locale date after a week", () => {
    const iso = ago(10 * 24 * 60 * 60 * 1000);
    expect(formatRelativeTime(iso)).toBe(new Date(iso).toLocaleDateString());
  });
});

describe("formatFileSize", () => {
  it.each([
    [0, "0 B"],
    [512, "512 B"],
    [1024, "1 KB"],
    [1536, "1.5 KB"],
    [10 * 1024 * 1024 * 1024, "10 GB"],
  ])("formats %d bytes as %s", (bytes, expected) => {
    expect(formatFileSize(bytes)).toBe(expected);
  });
});

describe("getInitials", () => {
  it("uses the first letter of up to two words, uppercased", () => {
    expect(getInitials("olive otter")).toBe("OO");
    expect(getInitials("Ada Byron Lovelace")).toBe("AB");
    expect(getInitials("Cher")).toBe("C");
  });
});

describe("truncate / cn", () => {
  it("truncates with an ellipsis only past the limit", () => {
    expect(truncate("short", 10)).toBe("short");
    expect(truncate("a very long file name.txt", 10)).toBe("a very ...");
  });

  it("joins truthy class names", () => {
    expect(cn("a", false && "b", "c")).toBe("a c");
  });
});
