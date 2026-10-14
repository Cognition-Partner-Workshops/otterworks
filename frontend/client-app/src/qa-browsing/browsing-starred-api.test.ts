import { beforeEach, describe, expect, it } from "vitest";
import { starredApi } from "@/lib/api";

const KEY = "otter_starred_items";

describe("browsing starredApi (localStorage-backed)", () => {
  beforeEach(() => localStorage.clear());

  it("starts with nothing starred", () => {
    expect(starredApi.isStarred("u1", "f1")).toBe(false);
    expect(starredApi.getStarredIds("u1")).toEqual({ fileIds: [], folderIds: [], documentIds: [] });
  });

  it("toggle stars then unstars an item", () => {
    expect(starredApi.toggle("u1", "f1", "file")).toBe(true);
    expect(starredApi.isStarred("u1", "f1")).toBe(true);
    expect(starredApi.toggle("u1", "f1", "file")).toBe(false);
    expect(starredApi.isStarred("u1", "f1")).toBe(false);
  });

  it("buckets starred ids by item type", () => {
    starredApi.toggle("u1", "f1", "file");
    starredApi.toggle("u1", "d1", "folder");
    starredApi.toggle("u1", "doc1", "document");
    expect(starredApi.getStarredIds("u1")).toEqual({
      fileIds: ["f1"],
      folderIds: ["d1"],
      documentIds: ["doc1"],
    });
  });

  it("isolates starred items per user", () => {
    starredApi.toggle("u1", "f1", "file");
    expect(starredApi.isStarred("u2", "f1")).toBe(false);
    expect(starredApi.getStarredIds("u2").fileIds).toEqual([]);
  });

  it("does not leak ids for users whose id is a prefix of another", () => {
    starredApi.toggle("u10", "f1", "file");
    expect(starredApi.getStarredIds("u1").fileIds).toEqual([]);
  });

  it("persists under the otter_starred_items key", () => {
    starredApi.toggle("u1", "f1", "file");
    const raw = JSON.parse(localStorage.getItem(KEY) ?? "{}");
    expect(Object.keys(raw)).toEqual(["u1:f1"]);
    expect(raw["u1:f1"]).toMatchObject({ itemId: "f1", itemType: "file" });
  });

  it("tolerates corrupt storage", () => {
    localStorage.setItem(KEY, "{not json");
    expect(starredApi.isStarred("u1", "f1")).toBe(false);
    expect(starredApi.toggle("u1", "f1", "file")).toBe(true);
  });
});
