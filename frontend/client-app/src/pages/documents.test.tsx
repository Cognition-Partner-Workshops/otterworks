import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import DocumentsPage from "./documents";
import { documentsApi } from "@/lib/api";
import type { Document } from "@/types";

vi.mock("@/lib/api", () => ({
  documentsApi: {
    list: vi.fn(),
    create: vi.fn(),
    delete: vi.fn(),
  },
  starredApi: {
    isStarred: vi.fn(() => false),
    toggle: vi.fn(),
  },
}));
vi.mock("@/components/ui/notification-bell", () => ({
  NotificationBell: () => null,
}));

const mockedApi = vi.mocked(documentsApi);
const documents: Document[] = [
  {
    id: "banana",
    title: "banana notes",
    content: "Banana document",
    ownerId: "owner-1",
    ownerName: "Owner",
    parentId: null,
    sharedWith: [],
    collaborators: [],
    tags: [],
    wordCount: 2,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-02T00:00:00.000Z",
  },
  {
    id: "apple",
    title: "Apple plan",
    content: "Apple document",
    ownerId: "owner-1",
    ownerName: "Owner",
    parentId: null,
    sharedWith: [],
    collaborators: [],
    tags: [],
    wordCount: 2,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-03T00:00:00.000Z",
  },
  {
    id: "cherry",
    title: "cherry draft",
    content: "Cherry document",
    ownerId: "owner-1",
    ownerName: "Owner",
    parentId: null,
    sharedWith: [],
    collaborators: [],
    tags: [],
    wordCount: 2,
    createdAt: "2026-01-01T00:00:00.000Z",
    updatedAt: "2026-01-04T00:00:00.000Z",
  },
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.list.mockResolvedValue({
    data: documents,
    total: documents.length,
    page: 1,
    pageSize: documents.length,
    hasMore: false,
  });
});

describe("Documents page", () => {
  it("sorts by last edited by default and supports case-insensitive title order", async () => {
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <DocumentsPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await screen.findByText("cherry draft");
    const sortSelect = screen.getByRole("combobox", { name: "Sort documents" });
    const getDocumentTitles = () =>
      screen
        .getAllByText(/^(Apple plan|banana notes|cherry draft)$/i)
        .map((element) => element.textContent);

    expect(sortSelect).toHaveValue("updatedAt-desc");
    expect(getDocumentTitles()).toEqual(["cherry draft", "Apple plan", "banana notes"]);

    fireEvent.change(sortSelect, { target: { value: "title-asc" } });

    expect(getDocumentTitles()).toEqual(["Apple plan", "banana notes", "cherry draft"]);
  });
});
