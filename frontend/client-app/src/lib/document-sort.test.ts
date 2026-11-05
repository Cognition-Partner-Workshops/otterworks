import { describe, it, expect } from "vitest";
import type { Document } from "@/types";
import {
  DEFAULT_DOCUMENT_SORT,
  DOCUMENT_SORT_API_ORDER,
  DOCUMENT_SORT_OPTIONS,
  parseDocumentSort,
  sortDocuments,
} from "./document-sort";

function makeDocument(overrides: Partial<Document> & Pick<Document, "id" | "title">): Document {
  return {
    content: "",
    ownerId: "u1",
    ownerName: "Olive Otter",
    parentId: null,
    sharedWith: [],
    collaborators: [],
    tags: [],
    wordCount: 0,
    createdAt: "2026-01-01T00:00:00Z",
    updatedAt: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

const documents: Document[] = [
  makeDocument({
    id: "a",
    title: "beta plan",
    createdAt: "2026-03-01T00:00:00Z",
    updatedAt: "2026-03-05T00:00:00Z",
  }),
  makeDocument({
    id: "b",
    title: "Alpha notes",
    createdAt: "2026-01-10T00:00:00Z",
    updatedAt: "2026-04-01T00:00:00Z",
  }),
  makeDocument({
    id: "c",
    title: "Chapter 10",
    createdAt: "2026-05-20T00:00:00Z",
    updatedAt: "2026-02-01T00:00:00Z",
  }),
  makeDocument({
    id: "d",
    title: "Chapter 2",
    createdAt: "2026-02-15T00:00:00Z",
    updatedAt: "2026-01-15T00:00:00Z",
  }),
];

const ids = (docs: Document[]) => docs.map((doc) => doc.id);

describe("document sort options", () => {
  it("offers Last edited, Name A to Z and Date created with Last edited as default", () => {
    expect(DOCUMENT_SORT_OPTIONS.map((option) => option.label)).toEqual([
      "Last edited",
      "Name A to Z",
      "Date created",
    ]);
    expect(DEFAULT_DOCUMENT_SORT).toBe("updated");
  });
});

describe("parseDocumentSort", () => {
  it("accepts every known sort value", () => {
    expect(parseDocumentSort("updated")).toBe("updated");
    expect(parseDocumentSort("name")).toBe("name");
    expect(parseDocumentSort("created")).toBe("created");
  });

  it("falls back to the default for missing or unknown values", () => {
    expect(parseDocumentSort(null)).toBe("updated");
    expect(parseDocumentSort(undefined)).toBe("updated");
    expect(parseDocumentSort("")).toBe("updated");
    expect(parseDocumentSort("size")).toBe("updated");
    expect(parseDocumentSort("NAME")).toBe("updated");
  });
});

describe("DOCUMENT_SORT_API_ORDER", () => {
  it("maps each option to the document-service sort column and direction", () => {
    expect(DOCUMENT_SORT_API_ORDER).toEqual({
      updated: { sort: "updated_at", direction: "desc" },
      name: { sort: "title", direction: "asc" },
      created: { sort: "created_at", direction: "desc" },
    });
  });
});

describe("sortDocuments", () => {
  it("sorts by most recently edited first", () => {
    expect(ids(sortDocuments(documents, "updated"))).toEqual(["b", "a", "c", "d"]);
  });

  it("sorts by title A to Z, case-insensitively and with natural number order", () => {
    expect(ids(sortDocuments(documents, "name"))).toEqual(["b", "a", "d", "c"]);
  });

  it("sorts by most recently created first", () => {
    expect(ids(sortDocuments(documents, "created"))).toEqual(["c", "a", "d", "b"]);
  });

  it("does not mutate the input array", () => {
    const original = ids(documents);
    sortDocuments(documents, "name");
    expect(ids(documents)).toEqual(original);
  });

  it("keeps documents with missing or invalid dates at the end", () => {
    const withBadDate = [
      makeDocument({ id: "x", title: "X", updatedAt: "not-a-date", createdAt: "" }),
      ...documents,
    ];
    expect(ids(sortDocuments(withBadDate, "updated")).at(-1)).toBe("x");
    expect(ids(sortDocuments(withBadDate, "created")).at(-1)).toBe("x");
  });

  it("handles an empty list", () => {
    expect(sortDocuments([], "name")).toEqual([]);
  });
});
