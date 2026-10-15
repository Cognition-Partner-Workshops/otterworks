import { http, HttpResponse } from "msw";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { Breadcrumb } from "./breadcrumb";
import { Sidebar } from "./sidebar";
import { NotificationBell } from "@/components/ui/notification-bell";
import { authApi, filesApi, notificationsApi, starredApi } from "@/lib/api";
import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";
import { billingServer as server } from "../../test-setup";

const API = "http://localhost:3000/api/v1";

function withProviders(ui: React.ReactElement, path = "/dashboard") {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("Breadcrumb", () => {
  it("always links Home to the dashboard", () => {
    withProviders(<Breadcrumb items={[]} />);
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/dashboard");
  });

  it("links items with href and renders the current item as text", () => {
    withProviders(<Breadcrumb items={[{ label: "Files", href: "/files" }, { label: "Reports" }]} />);
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute("href", "/files");
    expect(screen.getByText("Reports")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Reports" })).not.toBeInTheDocument();
  });
});

describe("Sidebar", () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarOpen: true });
    useAuthStore.setState({
      user: { id: "u1", email: "otter@example.test", displayName: "Olive Otter" } as never,
      isAuthenticated: true,
      isLoading: false,
    });
  });

  it("renders every browsing destination", () => {
    withProviders(<Sidebar />);
    const expected: Record<string, string> = {
      Dashboard: "/dashboard",
      Recent: "/recent",
      Files: "/files",
      Documents: "/documents",
      Search: "/search",
      "Shared with me": "/shared",
      Starred: "/starred",
      Notifications: "/notifications",
      Trash: "/trash",
      Settings: "/settings",
    };
    for (const [label, href] of Object.entries(expected)) {
      expect(screen.getByRole("link", { name: label })).toHaveAttribute("href", href);
    }
  });

  it("marks the current route and its children active", () => {
    withProviders(<Sidebar />, "/files/abc");
    const files = screen.getByRole("link", { name: "Files" });
    const recent = screen.getByRole("link", { name: "Recent" });
    expect(files.className).not.toEqual(recent.className);
  });

  it("shows the signed-in user and collapses to icons", () => {
    withProviders(<Sidebar />);
    expect(screen.getByText("Olive Otter")).toBeInTheDocument();
    expect(screen.getByText("OO")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(useUIStore.getState().sidebarOpen).toBe(false);
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(screen.queryByText("Olive Otter")).not.toBeInTheDocument();
  });
});

describe("NotificationBell", () => {
  it("links to the notifications panel without a badge when nothing is unread", async () => {
    server.use(http.get(`${API}/notifications/unread-count`, () => HttpResponse.json({ count: 0 })));
    withProviders(<NotificationBell />);
    const link = screen.getByRole("link", { name: "Notifications" });
    expect(link).toHaveAttribute("href", "/notifications");
  });

  // [REAL] BROWSE-R4: notification-service returns { unreadCount }, client reads `count`.
  it.fails("shows the unread badge for the real notification-service payload", async () => {
    server.use(
      http.get(`${API}/notifications/unread-count`, () =>
        HttpResponse.json({ userId: "u1", unreadCount: 3 })
      )
    );
    withProviders(<NotificationBell />);
    expect(await screen.findByRole("link", { name: "Notifications (3 unread)" }, { timeout: 1500 })).toBeInTheDocument();
  });
});

describe("browsing API client contract", () => {
  it("requests file pages with page/page_size and computes hasMore", async () => {
    let query: URLSearchParams | undefined;
    server.use(
      http.get(`${API}/files`, ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json({ files: [], total: 120, page: 2, page_size: 50 });
      })
    );
    const result = await filesApi.list("folder-1", 2, 50);
    expect(query?.get("page")).toBe("2");
    expect(query?.get("page_size")).toBe("50");
    expect(query?.get("folder_id")).toBe("folder-1");
    expect(result.hasMore).toBe(true);
  });

  // [REAL] BROWSE-R5: notification-service paginates on page_size, client sends pageSize.
  it.fails("paginates notifications with the service's page_size param", async () => {
    let query: URLSearchParams | undefined;
    server.use(
      http.get(`${API}/notifications`, ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json({ data: [], total: 0, page: 1, pageSize: 20, hasMore: false });
      })
    );
    await notificationsApi.list(1, 20);
    expect(query?.get("page_size")).toBe("20");
  });

  // [REAL] BROWSE-R3: service routes PUT /notifications/{id}/read only.
  it.fails("marks one notification read with PUT", async () => {
    server.use(http.put(`${API}/notifications/n1/read`, () => new HttpResponse(null, { status: 204 })));
    await notificationsApi.markRead("n1");
  });

  // [REAL] BROWSE-R2: service routes PUT /notifications/read-all only.
  it.fails("marks all notifications read with PUT", async () => {
    server.use(http.put(`${API}/notifications/read-all`, () => HttpResponse.json({ markedCount: 1 })));
    await notificationsApi.markAllRead();
  });

  // [REAL] BROWSE-R1: auth-service maps PUT /auth/profile only.
  it.fails("saves the profile with PUT", async () => {
    server.use(
      http.put(`${API}/auth/profile`, () =>
        HttpResponse.json({ id: "u1", email: "a@example.test", displayName: "New" })
      )
    );
    await authApi.updateProfile({ displayName: "New" });
  });
});

describe("starredApi", () => {
  afterEach(() => localStorage.clear());

  it("toggles stars per user and groups ids by type", () => {
    expect(starredApi.toggle("u1", "f1", "file")).toBe(true);
    starredApi.toggle("u1", "d1", "folder");
    starredApi.toggle("u1", "doc1", "document");
    starredApi.toggle("u2", "f2", "file");

    expect(starredApi.isStarred("u1", "f1")).toBe(true);
    expect(starredApi.isStarred("u2", "f1")).toBe(false);
    expect(starredApi.getStarredIds("u1")).toEqual({
      fileIds: ["f1"],
      folderIds: ["d1"],
      documentIds: ["doc1"],
    });

    expect(starredApi.toggle("u1", "f1", "file")).toBe(false);
    expect(starredApi.getStarredIds("u1").fileIds).toEqual([]);
  });

  it("survives corrupt localStorage", async () => {
    localStorage.setItem("otter_starred_items", "{not json");
    await waitFor(() => expect(starredApi.getStarredIds("u1").fileIds).toEqual([]));
  });
});
