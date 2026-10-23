import { http, HttpResponse } from "msw";
import { fireEvent, screen, within } from "@testing-library/react";
import { Route, Routes, useLocation } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import FilesPage from "./files";
import { billingServer } from "../test-setup";
import { API, isoDaysAgo, rawFile, renderAt, resetStores } from "@/test/browsing-helpers";

const folders: Record<string, { id: string; name: string; parent_id: string | null }> = {
  root1: { id: "root1", name: "Projects", parent_id: null },
  child1: { id: "child1", name: "Q3 Launch", parent_id: "root1" },
};

function mockTree() {
  billingServer.use(
    http.get(`${API}/folders/:id`, ({ params }) => {
      const f = folders[params.id as string];
      return f ? HttpResponse.json({ ...f, owner_id: "user-1" }) : HttpResponse.json({ error: "not found" }, { status: 404 });
    }),
    http.get(`${API}/folders`, ({ request }) => {
      const parent = new URL(request.url).searchParams.get("parent_id");
      return HttpResponse.json({
        folders: Object.values(folders).filter((f) => f.parent_id === (parent ?? null)),
      });
    }),
    http.get(`${API}/files`, ({ request }) => {
      const folder = new URL(request.url).searchParams.get("folder_id");
      const files = folder === "child1" ? [rawFile("f1", "plan.txt", isoDaysAgo(0))] : [];
      return HttpResponse.json({ files, total: files.length, page: 1, page_size: 50 });
    }),
    http.get(`${API}/notifications/unread-count`, () => HttpResponse.json({ count: 0 }))
  );
}

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname + loc.search}</div>;
}

function FilesWithProbe() {
  return (
    <>
      <FilesPage />
      <Routes>
        <Route path="*" element={<LocationProbe />} />
      </Routes>
    </>
  );
}

describe("Files page browsing (folder drill-down + breadcrumbs)", () => {
  beforeEach(() => {
    resetStores();
    mockTree();
  });

  it("shows no breadcrumb at the root", async () => {
    renderAt(<FilesPage />, { path: "/files" });
    expect(await screen.findByText("Projects")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Breadcrumb" })).not.toBeInTheDocument();
  });

  it("links root folders to ?folder=<id>", async () => {
    renderAt(<FilesPage />, { path: "/files" });
    expect((await screen.findByText("Projects")).closest("a")).toHaveAttribute(
      "href",
      "/files?folder=root1"
    );
  });

  it("deep link to a folder shows Files > <folder> breadcrumb", async () => {
    renderAt(<FilesPage />, { path: "/files?folder=root1" });
    const crumb = await screen.findByRole("navigation", { name: "Breadcrumb" });
    expect(await screen.findByText("Q3 Launch")).toBeInTheDocument();
    expect(crumb).toHaveTextContent("FilesProjects");
    expect(within(crumb).getByRole("link", { name: "Files" })).toHaveAttribute("href", "/files");
  });

  it("drilling into a nested folder updates the URL and lists its files", async () => {
    renderAt(<FilesWithProbe />, { path: "/files?folder=root1" });
    fireEvent.click(await screen.findByText("Q3 Launch"));
    expect(await screen.findByText("plan.txt")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent("/files?folder=child1");
  });

  it("breadcrumb Files link returns to the root listing", async () => {
    renderAt(<FilesWithProbe />, { path: "/files?folder=root1" });
    const crumb = await screen.findByRole("navigation", { name: "Breadcrumb" });
    fireEvent.click(within(crumb).getByRole("link", { name: "Files" }));
    expect(await screen.findByText("Projects")).toBeInTheDocument();
    expect(screen.getByTestId("location")).toHaveTextContent(/^\/files$/);
    expect(screen.queryByRole("navigation", { name: "Breadcrumb" })).not.toBeInTheDocument();
  });

  it("shows the empty-folder state for a folder with no children", async () => {
    billingServer.use(
      http.get(`${API}/files`, () => HttpResponse.json({ files: [], total: 0, page: 1, page_size: 50 }))
    );
    renderAt(<FilesPage />, { path: "/files?folder=child1" });
    expect(await screen.findByText("This folder is empty")).toBeInTheDocument();
  });
});
