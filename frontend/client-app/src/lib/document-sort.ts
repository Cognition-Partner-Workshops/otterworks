import type { Document } from "@/types";

export const DOCUMENT_SORT_OPTIONS = [
  { value: "updated", label: "Last edited" },
  { value: "name", label: "Name A to Z" },
  { value: "created", label: "Date created" },
] as const;

export type DocumentSortOption = (typeof DOCUMENT_SORT_OPTIONS)[number]["value"];

export const DEFAULT_DOCUMENT_SORT: DocumentSortOption = "updated";

export function parseDocumentSort(value: string | null | undefined): DocumentSortOption {
  const match = DOCUMENT_SORT_OPTIONS.find((option) => option.value === value);
  return match ? match.value : DEFAULT_DOCUMENT_SORT;
}

function toTimestamp(value: string | undefined): number {
  const time = value ? Date.parse(value) : Number.NaN;
  return Number.isNaN(time) ? 0 : time;
}

const titleCollator = new Intl.Collator(undefined, { sensitivity: "base", numeric: true });

const comparators: Record<DocumentSortOption, (a: Document, b: Document) => number> = {
  updated: (a, b) => toTimestamp(b.updatedAt) - toTimestamp(a.updatedAt),
  name: (a, b) => titleCollator.compare(a.title ?? "", b.title ?? ""),
  created: (a, b) => toTimestamp(b.createdAt) - toTimestamp(a.createdAt),
};

export function sortDocuments(documents: readonly Document[], sort: DocumentSortOption): Document[] {
  return [...documents].sort(comparators[sort]);
}
