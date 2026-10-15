import { http, HttpResponse } from "msw";
import { screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import RecentPage from "./recent";
import { billingServer } from "../test-setup";
import {
  API,
  isoDaysAgo,
  rawDocument,
  rawFile,
  renderAt,
  resetStores,
} from "@/test/browsing-helpers";

function mockRecent(files: unknown[], documents: unknown[]) {
  billingServer.use(
    http.get(`${API}/files`, () =>
      HttpResponse.json({ files, total: files.length, page: 1, page_size: 50 })
    ),
    http.get(`${API}/documents`, () =>
      HttpResponse.json({ items: documents, total: documents.length })
    ),
    http.get(`${API}/notifications/unread-count`, () => HttpResponse.json({ count: 0 }))
  );
}

describe("Recent page", () => {
  beforeEach(() => resetStores());

  it("shows the empty state when nothing was touched recently", async () => {
    mockRecent([], []);
    renderAt(<RecentPage />, { path: "/recent" });
    expect(await screen.findByText("No recent items")).toBeInTheDocument();
  });

  it("merges files and documents into time buckets", async () => {
    mockRecent(
      [rawFile("f1", "today.txt", isoDaysAgo(0)), rawFile("f2", "ancient.txt", isoDaysAgo(60))],
      [rawDocument("d1", "Old plan", isoDaysAgo(60))]
    );
    renderAt(<RecentPage />, { path: "/recent" });
    const today = (await screen.findByRole("heading", { name: "Today" })).closest("section")!;
    expect(within(today).getByText("today.txt")).toBeInTheDocument();
    const earlier = screen.getByRole("heading", { name: "Earlier" }).closest("section")!;
    expect(within(earlier).getByText("ancient.txt")).toBeInTheDocument();
    expect(within(earlier).getByText("Old plan")).toBeInTheDocument();
    expect(screen.queryByText("No recent items")).not.toBeInTheDocument();
  });

  it("omits empty buckets", async () => {
    mockRecent([rawFile("f1", "today.txt", isoDaysAgo(0))], []);
    renderAt(<RecentPage />, { path: "/recent" });
    await screen.findByRole("heading", { name: "Today" });
    expect(screen.queryByRole("heading", { name: "Yesterday" })).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Earlier" })).not.toBeInTheDocument();
  });

  it("orders items newest first within a bucket", async () => {
    mockRecent(
      [
        rawFile("f-old", "older.txt", isoDaysAgo(40)),
        rawFile("f-new", "newer.txt", isoDaysAgo(30)),
      ],
      []
    );
    renderAt(<RecentPage />, { path: "/recent" });
    const earlier = (await screen.findByRole("heading", { name: "Earlier" })).closest("section")!;
    const text = earlier.textContent ?? "";
    expect(text.indexOf("newer.txt")).toBeLessThan(text.indexOf("older.txt"));
  });

  it("links file cards to the file detail and document cards to the editor", async () => {
    mockRecent([rawFile("f1", "today.txt", isoDaysAgo(0))], [rawDocument("d1", "Plan", isoDaysAgo(0))]);
    renderAt(<RecentPage />, { path: "/recent" });
    expect((await screen.findByText("today.txt")).closest("a")).toHaveAttribute("href", "/files/f1");
    expect(screen.getByText("Plan").closest("a")).toHaveAttribute("href", "/documents/d1");
  });
});
