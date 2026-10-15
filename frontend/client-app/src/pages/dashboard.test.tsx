import { http, HttpResponse } from "msw";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import DashboardPage from "./dashboard";
import { billingServer } from "../test-setup";
import {
  API,
  isoDaysAgo,
  rawDocument,
  rawFile,
  renderAt,
  resetStores,
} from "@/test/browsing-helpers";

function mockDashboard({
  files = [] as unknown[],
  documents = [] as unknown[],
  activity = [] as unknown[],
} = {}) {
  billingServer.use(
    http.get(`${API}/files/activity`, () => HttpResponse.json({ items: activity })),
    http.get(`${API}/files`, () =>
      HttpResponse.json({ files, total: files.length, page: 1, page_size: 100 })
    ),
    http.get(`${API}/documents`, () =>
      HttpResponse.json({ items: documents, total: documents.length })
    ),
    http.get(`${API}/notifications/unread-count`, () => HttpResponse.json({ count: 0 }))
  );
}

describe("Dashboard page", () => {
  beforeEach(() => resetStores());

  it("renders the header with quick actions", async () => {
    mockDashboard();
    renderAt(<DashboardPage />, { path: "/dashboard" });
    expect(await screen.findByRole("heading", { name: "Dashboard", level: 1 })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Upload file/ })).toHaveAttribute("href", "/files");
    expect(screen.getByRole("link", { name: /New document/ })).toHaveAttribute("href", "/documents");
  });

  it("shows empty states for a new user", async () => {
    mockDashboard();
    renderAt(<DashboardPage />, { path: "/dashboard" });
    expect(await screen.findByText("No recent files")).toBeInTheDocument();
    expect(screen.getByText("No recent documents")).toBeInTheDocument();
    expect(screen.getByText("No recent activity")).toBeInTheDocument();
  });

  it("computes stat cards from file and document totals", async () => {
    mockDashboard({
      files: [rawFile("f1", "a.txt", isoDaysAgo(0), 1024), rawFile("f2", "b.txt", isoDaysAgo(0), 1024)],
      documents: [rawDocument("d1", "Doc", isoDaysAgo(0))],
    });
    renderAt(<DashboardPage />, { path: "/dashboard" });
    const totalFiles = (await screen.findByText("Total files")).parentElement!;
    expect(totalFiles).toHaveTextContent("2");
    expect(await screen.findByText("2 KB of 10 GB")).toBeInTheDocument();
  });

  it("lists recent files and documents with View all links", async () => {
    mockDashboard({
      files: [rawFile("f1", "report.pdf", isoDaysAgo(0))],
      documents: [rawDocument("d1", "Roadmap", isoDaysAgo(0))],
    });
    renderAt(<DashboardPage />, { path: "/dashboard" });
    expect((await screen.findByText("report.pdf")).closest("a")).toHaveAttribute("href", "/files/f1");
    expect(screen.getByText("Roadmap").closest("a")).toHaveAttribute("href", "/documents/d1");
    const viewAll = screen.getAllByRole("link", { name: /View all/ }).map((a) => a.getAttribute("href"));
    expect(viewAll).toEqual(["/files", "/documents"]);
  });

  it("renders the activity feed", async () => {
    mockDashboard({
      activity: [
        {
          id: "a1",
          type: "upload",
          description: "uploaded report.pdf",
          actor_name: "Olive Otter",
          resource_name: "report.pdf",
          resource_type: "file",
          resource_id: "f1",
          created_at: isoDaysAgo(0),
        },
      ],
    });
    renderAt(<DashboardPage />, { path: "/dashboard" });
    expect(await screen.findByText("uploaded report.pdf")).toBeInTheDocument();
    expect(screen.queryByText("No recent activity")).not.toBeInTheDocument();
  });
});
