import { http, HttpResponse } from "msw";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import type { ReactElement } from "react";
import FilesPage from "@/pages/files";
import TrashPage from "@/pages/trash";
import RecentPage from "@/pages/recent";
import StarredPage from "@/pages/starred";
import DashboardPage from "@/pages/dashboard";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { starredApi } from "@/lib/api";
import { billingServer as server } from "../test-setup";

const API = "http://localhost:3000/api/v1";
const now = Date.now();
const iso = (msAgo: number) => new Date(now - msAgo).toISOString();
const DAY = 86_400_000;

function rawFile(over: Record<string, unknown> = {}) {
  return {
    id: "f1",
    name: "a.txt",
    mime_type: "text/plain",
    size_bytes: 10,
    folder_id: null,
    owner_id: "u1",
    is_trashed: false,
    created_at: iso(DAY),
    updated_at: iso(DAY),
    ...over,
  };
}

function fallbackHandlers() {
  return [
    http.get(`${API}/notifications/unread-count`, () => HttpResponse.json({ count: 0 })),
    http.get(`${API}/files/activity`, () => HttpResponse.json({ items: [] })),
    http.get(`${API}/documents`, () => HttpResponse.json({ items: [], total: 0, page: 1, size: 50, pages: 1 })),
    http.get(`${API}/files`, () => HttpResponse.json({ files: [], total: 0, page: 1, page_size: 50 })),
    http.get(`${API}/folders`, () => HttpResponse.json({ folders: [] })),
    http.get(`${API}/files/trash`, () => HttpResponse.json({ files: [], total: 0, page: 1, page_size: 50 })),
    http.get(`${API}/search/*`, () => HttpResponse.json({ results: [], hits: [] })),
  ];
}

function renderRoute(element: ReactElement, path: string, route = path.split("?")[0]) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path={route} element={element} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

beforeEach(() => {
  server.use(...fallbackHandlers());
  useUIStore.setState({ viewMode: "grid", sortConfig: { field: "updatedAt", direction: "desc" }, sidebarOpen: true });
  useAuthStore.setState({
    user: { id: "u1", email: "qa@example.test", displayName: "QA User" },
    isAuthenticated: true,
    isLoading: false,
  });
});
afterEach(() => localStorage.clear());

describe("browsing Files page", () => {
  it("shows the empty state for an empty root", async () => {
    renderRoute(<FilesPage />, "/files");
    expect(await screen.findByText("This folder is empty")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Breadcrumb" })).not.toBeInTheDocument();
  });

  it("renders folders and files at the root", async () => {
    server.use(
      http.get(`${API}/files`, () => HttpResponse.json({ files: [rawFile({ name: "root.txt" })], total: 1 })),
      http.get(`${API}/folders`, () => HttpResponse.json({ folders: [{ id: "d1", name: "Projects", owner_id: "u1" }] }))
    );
    renderRoute(<FilesPage />, "/files");
    expect(await screen.findByText("root.txt")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
  });

  it("deep link /files?folder=<id> scopes requests and renders a Files > folder breadcrumb", async () => {
    const seen: Record<string, string | null> = {};
    server.use(
      http.get(`${API}/files`, ({ request }) => {
        seen.files = new URL(request.url).searchParams.get("folder_id");
        return HttpResponse.json({ files: [rawFile({ name: "nested.txt", folder_id: "d1" })], total: 1 });
      }),
      http.get(`${API}/folders`, ({ request }) => {
        seen.folders = new URL(request.url).searchParams.get("parent_id");
        return HttpResponse.json({ folders: [] });
      }),
      http.get(`${API}/folders/d1`, () => HttpResponse.json({ id: "d1", name: "Projects", parent_id: null }))
    );
    renderRoute(<FilesPage />, "/files?folder=d1", "/files");
    expect(await screen.findByText("nested.txt")).toBeInTheDocument();
    expect(seen).toEqual({ files: "d1", folders: "d1" });
    const nav = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(within(nav).getByRole("link", { name: "Files" })).toHaveAttribute("href", "/files");
    expect(await within(nav).findByText("Projects")).toBeInTheDocument();
  });

  it("links folder cards to their deep link", async () => {
    server.use(http.get(`${API}/folders`, () => HttpResponse.json({ folders: [{ id: "d1", name: "Projects" }] })));
    renderRoute(<FilesPage />, "/files");
    const label = await screen.findByText("Projects");
    const link = label.closest("a");
    expect(link).not.toBeNull();
    expect(link!.getAttribute("href")).toBe("/files?folder=d1");
  });

  const sortFixture = [
    rawFile({ id: "1", name: "bravo.txt", size_bytes: 300, updated_at: iso(3 * DAY), created_at: iso(1 * DAY) }),
    rawFile({ id: "2", name: "alpha.txt", size_bytes: 100, updated_at: iso(1 * DAY), created_at: iso(3 * DAY) }),
    rawFile({ id: "3", name: "charlie.txt", size_bytes: 200, updated_at: iso(2 * DAY), created_at: iso(2 * DAY) }),
  ];

  function fileOrder() {
    return screen.getAllByText(/^(alpha|bravo|charlie)\.txt$/).map((el) => el.textContent);
  }

  it.each([
    ["updatedAt-desc", ["alpha.txt", "charlie.txt", "bravo.txt"]],
    ["updatedAt-asc", ["bravo.txt", "charlie.txt", "alpha.txt"]],
    ["name-asc", ["alpha.txt", "bravo.txt", "charlie.txt"]],
    ["name-desc", ["charlie.txt", "bravo.txt", "alpha.txt"]],
    ["size-desc", ["bravo.txt", "charlie.txt", "alpha.txt"]],
    ["size-asc", ["alpha.txt", "charlie.txt", "bravo.txt"]],
    ["createdAt-desc", ["bravo.txt", "charlie.txt", "alpha.txt"]],
    ["createdAt-asc", ["alpha.txt", "charlie.txt", "bravo.txt"]],
  ])("sort option %s orders files correctly", async (value, expected) => {
    server.use(http.get(`${API}/files`, () => HttpResponse.json({ files: sortFixture, total: 3 })));
    renderRoute(<FilesPage />, "/files");
    await screen.findByText("alpha.txt");
    fireEvent.change(screen.getByDisplayValue("Last modified"), { target: { value } });
    await waitFor(() => expect(fileOrder()).toEqual(expected));
  });
});

describe("browsing Trash page", () => {
  it("shows the empty state", async () => {
    renderRoute(<TrashPage />, "/trash");
    expect(await screen.findByText("Trash is empty")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Empty Trash/ })).not.toBeInTheDocument();
  });

  it("lists trashed items with Empty Trash available", async () => {
    server.use(
      http.get(`${API}/files/trash`, () =>
        HttpResponse.json({ files: [rawFile({ id: "t1", name: "old.txt", is_trashed: true })], total: 1 })
      )
    );
    renderRoute(<TrashPage />, "/trash");
    expect(await screen.findByText("old.txt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Empty Trash/ })).toBeInTheDocument();
  });

  it("restores an item and refreshes the list", async () => {
    let trashed = true;
    let restoredId = "";
    server.use(
      http.get(`${API}/files/trash`, () =>
        HttpResponse.json(
          trashed
            ? { files: [rawFile({ id: "t1", name: "old.txt", is_trashed: true })], total: 1 }
            : { files: [], total: 0 }
        )
      ),
      http.post(`${API}/files/:id/restore`, ({ params }) => {
        restoredId = String(params.id);
        trashed = false;
        return HttpResponse.json(rawFile({ id: "t1" }));
      })
    );
    renderRoute(<TrashPage />, "/trash");
    await screen.findByText("old.txt");
    fireEvent.click(screen.getByRole("button", { name: /Restore/ }));
    expect(await screen.findByText("Trash is empty")).toBeInTheDocument();
    expect(restoredId).toBe("t1");
  });
});

describe("browsing Recent page", () => {
  it("shows the empty state", async () => {
    renderRoute(<RecentPage />, "/recent");
    expect(await screen.findByText("No recent items")).toBeInTheDocument();
  });

  it("groups files and documents by time bucket, newest first", async () => {
    server.use(
      http.get(`${API}/files`, () =>
        HttpResponse.json({
          files: [
            rawFile({ id: "old", name: "ancient.txt", updated_at: iso(40 * DAY) }),
            rawFile({ id: "new", name: "fresh.txt", updated_at: iso(60_000) }),
          ],
          total: 2,
        })
      ),
      http.get(`${API}/documents`, () =>
        HttpResponse.json({ items: [{ id: "doc1", title: "Fresh Doc", updated_at: iso(30_000), created_at: iso(30_000) }], total: 1 })
      )
    );
    renderRoute(<RecentPage />, "/recent");
    expect(await screen.findByText("fresh.txt")).toBeInTheDocument();
    expect(screen.getByText("Today")).toBeInTheDocument();
    expect(screen.getByText("Earlier")).toBeInTheDocument();
    const text = document.body.textContent ?? "";
    expect(text.indexOf("Fresh Doc")).toBeLessThan(text.indexOf("fresh.txt"));
    expect(text.indexOf("fresh.txt")).toBeLessThan(text.indexOf("ancient.txt"));
  });
});

describe("browsing Starred page", () => {
  it("shows the empty state when nothing is starred", async () => {
    renderRoute(<StarredPage />, "/starred");
    expect(await screen.findByText("No starred items")).toBeInTheDocument();
  });

  it("shows starred files and silently drops ones that no longer exist", async () => {
    starredApi.toggle("u1", "f1", "file");
    starredApi.toggle("u1", "gone", "file");
    server.use(
      http.get(`${API}/files/f1`, () => HttpResponse.json(rawFile({ id: "f1", name: "starred.txt" }))),
      http.get(`${API}/files/gone`, () => HttpResponse.json({ error: "file_not_found" }, { status: 404 }))
    );
    renderRoute(<StarredPage />, "/starred");
    expect(await screen.findByText("starred.txt")).toBeInTheDocument();
    expect(screen.queryByText("No starred items")).not.toBeInTheDocument();
  });

  it("does not show another user's starred items", async () => {
    starredApi.toggle("someone-else", "f1", "file");
    renderRoute(<StarredPage />, "/starred");
    expect(await screen.findByText("No starred items")).toBeInTheDocument();
  });
});

describe("browsing Dashboard page", () => {
  it("shows empty states for a brand-new account", async () => {
    renderRoute(<DashboardPage />, "/dashboard");
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText("No recent files")).toBeInTheDocument();
    expect(await screen.findByText("No recent documents")).toBeInTheDocument();
    expect(await screen.findByText("No recent activity")).toBeInTheDocument();
  });

  it("links through to the Files and Documents pages", async () => {
    renderRoute(<DashboardPage />, "/dashboard");
    await screen.findByRole("heading", { name: "Dashboard" });
    const hrefs = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    expect(hrefs).toContain("/files");
    expect(hrefs).toContain("/documents");
  });

  it("lists recent files from the API", async () => {
    server.use(http.get(`${API}/files`, () => HttpResponse.json({ files: [rawFile({ name: "dash.txt" })], total: 1 })));
    renderRoute(<DashboardPage />, "/dashboard");
    expect(await screen.findByText("dash.txt")).toBeInTheDocument();
  });
});
