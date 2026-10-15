import type { ReactNode } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

const search = vi.fn();
vi.mock("@/lib/api", () => ({ searchApi: { search: (...args: unknown[]) => search(...args) } }));
vi.mock("@/components/layout/app-shell", () => ({ AppShell: ({ children }: { children: ReactNode }) => <>{children}</> }));

import SearchPage from "./search";

function renderPage(path = "/search") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <SearchPage />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const page = (data: unknown[]) => ({ data, total: data.length, page: 1, pageSize: 20, hasMore: false });

describe("SearchPage", () => {
  beforeEach(() => search.mockReset());

  it("shows the empty state and does not query before searching", () => {
    renderPage();
    expect(screen.getByText("Search OtterWorks")).toBeInTheDocument();
    expect(search).not.toHaveBeenCalled();
  });

  it("runs the ?q= query from the URL and links results by type", async () => {
    search.mockResolvedValue(
      page([
        { id: "d1", type: "document", name: "Otter plan", snippet: "", path: "", updatedAt: "", ownerName: "" },
        { id: "f1", type: "file", name: "otter.png", snippet: "", path: "", updatedAt: "", ownerName: "" },
      ])
    );
    renderPage("/search?q=otter");
    expect(await screen.findByText("Otter plan")).toBeInTheDocument();
    expect(screen.getByText(/2 results for/)).toBeInTheDocument();
    expect(screen.getByText("Otter plan").closest("a")).toHaveAttribute("href", "/documents/d1");
    expect(screen.getByText("otter.png").closest("a")).toHaveAttribute("href", "/files/f1");
    expect(search).toHaveBeenCalledWith({ query: "otter", type: undefined });
  });

  it("submits a trimmed query and shows no-results state", async () => {
    search.mockResolvedValue(page([]));
    renderPage();
    const input = screen.getByPlaceholderText("Search files, documents, and folders...");
    fireEvent.change(input, { target: { value: "  zzz  " } });
    fireEvent.submit(input.closest("form") as HTMLFormElement);
    expect(await screen.findByText("No results found")).toBeInTheDocument();
    expect(search).toHaveBeenCalledWith({ query: "zzz", type: undefined });
  });

  it("re-queries with the selected type filter", async () => {
    search.mockResolvedValue(page([]));
    renderPage("/search?q=otter");
    await screen.findByText("No results found");
    fireEvent.click(screen.getAllByRole("button", { name: "" })[0]);
    fireEvent.click(screen.getByRole("button", { name: "Documents" }));
    await waitFor(() => expect(search).toHaveBeenLastCalledWith({ query: "otter", type: "document" }));
  });

  it("keeps <em> highlights and escapes other markup in snippets", async () => {
    search.mockResolvedValue(
      page([{ id: "d1", type: "document", name: "Doc", snippet: "<em>otter</em><img src=x onerror=alert(1)>", path: "", updatedAt: "", ownerName: "" }])
    );
    const { container } = renderPage("/search?q=otter");
    await screen.findByText("Doc");
    expect(container.querySelector("em")?.textContent).toBe("otter");
    expect(container.querySelector("img")).toBeNull();
  });

  it("clears the query with the X button", async () => {
    search.mockResolvedValue(page([]));
    renderPage("/search?q=otter");
    await screen.findByText("No results found");
    const buttons = screen.getAllByRole("button", { name: "" });
    fireEvent.click(buttons[buttons.length - 1]);
    expect(screen.getByText("Search OtterWorks")).toBeInTheDocument();
  });
});
