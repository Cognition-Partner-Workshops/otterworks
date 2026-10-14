import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import SearchPage from "./search";
import { SearchBar } from "@/components/ui/search-bar";
import { billingServer } from "../test-setup";

vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

const SEARCH_URL = "http://localhost:3000/api/v1/search";
const PLACEHOLDER = "Search files, documents, and folders...";

function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname + loc.search}</div>;
}

function renderSearch(initialPath = "/search") {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={[initialPath]}>
        <Routes>
          <Route path="/search" element={<SearchPage />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function mockSearch(handler: (url: URL) => Record<string, unknown>) {
  const seen: URL[] = [];
  billingServer.use(
    http.get(SEARCH_URL, ({ request }) => {
      const url = new URL(request.url);
      seen.push(url);
      return HttpResponse.json(handler(url));
    })
  );
  return seen;
}

function submit(query: string) {
  const input = screen.getByPlaceholderText(PLACEHOLDER);
  fireEvent.change(input, { target: { value: query } });
  fireEvent.submit(input.closest("form")!);
}

const doc = (id: string, title: string, snippet = "") => ({
  id,
  type: "document",
  title,
  content_snippet: snippet,
  updated_at: new Date().toISOString(),
});

describe("Search page (QA)", () => {
  it("shows the initial empty state and does not call the API", async () => {
    const seen = mockSearch(() => ({ results: [], total: 0 }));
    renderSearch();
    expect(screen.getByText("Search OtterWorks")).toBeInTheDocument();
    await new Promise((r) => setTimeout(r, 50));
    expect(seen).toHaveLength(0);
  });

  it("submits a query and renders results with a count", async () => {
    mockSearch(() => ({ results: [doc("d1", "Otter Plan"), doc("d2", "Otter Notes")], total: 2 }));
    renderSearch();
    submit("otter");
    expect(await screen.findByText("Otter Plan")).toBeInTheDocument();
    expect(screen.getByText("Otter Notes")).toBeInTheDocument();
    expect(screen.getByText(/2 results for/)).toBeInTheDocument();
  });

  it("uses singular 'result' for one hit", async () => {
    mockSearch(() => ({ results: [doc("d1", "Lonely Otter")], total: 1 }));
    renderSearch();
    submit("lonely");
    expect(await screen.findByText(/^1 result for/)).toBeInTheDocument();
  });

  it("pluralises the count from the total, not the page length", async () => {
    mockSearch(() => ({ results: [doc("d1", "Paged Otter")], total: 25 }));
    renderSearch();
    submit("paged");
    expect(await screen.findByText(/^25 results for/)).toBeInTheDocument();
  });

  it("trims the submitted query", async () => {
    const seen = mockSearch(() => ({ results: [], total: 0 }));
    renderSearch();
    submit("   spaced   ");
    await screen.findByText("No results found");
    expect(seen[0].searchParams.get("q")).toBe("spaced");
  });

  it("does not search for a whitespace-only query", async () => {
    const seen = mockSearch(() => ({ results: [], total: 0 }));
    renderSearch();
    submit("    ");
    await new Promise((r) => setTimeout(r, 50));
    expect(seen).toHaveLength(0);
    expect(screen.getByText("Search OtterWorks")).toBeInTheDocument();
  });

  it("shows the no-results state including the query", async () => {
    mockSearch(() => ({ results: [], total: 0 }));
    renderSearch();
    submit("xyznothing");
    expect(await screen.findByText("No results found")).toBeInTheDocument();
    expect(screen.getByText(/No results for "xyznothing"/)).toBeInTheDocument();
  });

  it("prefills and runs the query from ?q=", async () => {
    const seen = mockSearch(() => ({ results: [doc("d1", "From URL")], total: 1 }));
    renderSearch("/search?q=from%20url");
    expect(await screen.findByText("From URL")).toBeInTheDocument();
    expect(screen.getByPlaceholderText(PLACEHOLDER)).toHaveValue("from url");
    expect(seen[0].searchParams.get("q")).toBe("from url");
  });

  it("type filter chips re-query with the selected type", async () => {
    const seen = mockSearch(() => ({ results: [doc("d1", "Typed")], total: 1 }));
    renderSearch();
    submit("typed");
    await screen.findByText("Typed");
    const filterToggle = screen.getByPlaceholderText(PLACEHOLDER).closest("form")!.querySelector("button[type='button']")!;
    fireEvent.click(filterToggle);
    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    await waitFor(() => expect(seen.some((u) => u.searchParams.get("type") === "document")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "Files" }));
    await waitFor(() => expect(seen.some((u) => u.searchParams.get("type") === "file")).toBe(true));
    fireEvent.click(screen.getByRole("button", { name: "All types" }));
    await waitFor(() => expect(seen.at(-1)!.searchParams.has("type")).toBe(false));
  });

  it("clear button resets query and returns to the initial state", async () => {
    mockSearch(() => ({ results: [doc("d1", "Clear Me")], total: 1 }));
    renderSearch();
    submit("clear");
    await screen.findByText("Clear Me");
    const buttons = screen.getByPlaceholderText(PLACEHOLDER).closest("form")!.querySelectorAll("button[type='button']");
    fireEvent.click(buttons[buttons.length - 1]);
    expect(screen.getByPlaceholderText(PLACEHOLDER)).toHaveValue("");
    expect(await screen.findByText("Search OtterWorks")).toBeInTheDocument();
  });

  it("links each result type to the right route", async () => {
    mockSearch(() => ({
      results: [
        doc("doc-1", "A Doc"),
        { id: "file-1", type: "file", name: "a.txt" },
        { id: "fold-1", type: "folder", name: "A Folder" },
      ],
      total: 3,
    }));
    renderSearch();
    submit("a");
    expect((await screen.findByText("A Doc")).closest("a")).toHaveAttribute("href", "/documents/doc-1");
    expect(screen.getByText("a.txt").closest("a")).toHaveAttribute("href", "/files/file-1");
    expect(screen.getByText("A Folder").closest("a")).toHaveAttribute("href", "/files?folder=fold-1");
  });

  it("navigates to the document when a result is clicked", async () => {
    mockSearch(() => ({ results: [doc("doc-9", "Click Me")], total: 1 }));
    renderSearch();
    submit("click");
    fireEvent.click(await screen.findByText("Click Me"));
    expect(await screen.findByTestId("location")).toHaveTextContent("/documents/doc-9");
  });

  it("keeps <em> highlights but escapes other HTML in snippets", async () => {
    mockSearch(() => ({
      results: [doc("d1", "XSS Doc", 'safe <em>otter</em> <img src=x onerror="alert(1)"><script>x</script>')],
      total: 1,
    }));
    const { container } = renderSearch();
    submit("otter");
    await screen.findByText("XSS Doc");
    const snippet = container.querySelector("p.line-clamp-2")!;
    expect(snippet.querySelector("em")).toHaveTextContent("otter");
    expect(snippet.querySelector("img")).toBeNull();
    expect(snippet.querySelector("script")).toBeNull();
    expect(snippet.textContent).toContain("<img");
  });
});

describe("Header SearchBar (QA)", () => {
  function renderBar() {
    return render(
      <MemoryRouter initialEntries={["/dashboard"]}>
        <Routes>
          <Route path="/dashboard" element={<SearchBar />} />
          <Route path="*" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>
    );
  }

  it("navigates to /search with an encoded query", async () => {
    renderBar();
    const input = screen.getByPlaceholderText("Search files, documents...");
    fireEvent.change(input, { target: { value: " otter & co " } });
    fireEvent.submit(input.closest("form")!);
    expect(await screen.findByTestId("location")).toHaveTextContent("/search?q=otter%20%26%20co");
  });

  it("ignores empty submissions", () => {
    renderBar();
    const input = screen.getByPlaceholderText("Search files, documents...");
    fireEvent.submit(input.closest("form")!);
    expect(screen.queryByTestId("location")).toBeNull();
  });
});
