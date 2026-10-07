import type { ReactNode } from "react";
import { http, HttpResponse } from "msw";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import toast, { Toaster } from "react-hot-toast";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import DocumentsPage from "./documents";
import { billingServer as server } from "../test-setup";
import { useUIStore } from "@/stores/ui-store";

vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

const API = "http://localhost:3000/api/v1";

beforeAll(() => {
  // react-hot-toast reads prefers-reduced-motion, which jsdom does not implement.
  window.matchMedia ??= ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: () => {},
    removeListener: () => {},
    addEventListener: () => {},
    removeEventListener: () => {},
    dispatchEvent: () => false,
  })) as typeof window.matchMedia;
});

function doc(id: string, title: string, content = "") {
  return {
    id,
    title,
    content,
    content_type: "text/markdown",
    owner_id: "user-1",
    folder_id: null,
    is_deleted: false,
    is_template: false,
    word_count: content.split(" ").filter(Boolean).length,
    version: 1,
    created_at: "2026-10-07T03:00:00Z",
    updated_at: "2026-10-07T03:00:00Z",
  };
}

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <DocumentsPage />
        <Toaster />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function documentTitles() {
  return Array.from(
    document.querySelectorAll<HTMLElement>("a[href^='/documents/'] p.font-medium")
  ).map((title) => title.textContent);
}

async function openMenuFor(title: string) {
  const card = (await screen.findByText(title)).closest("a");
  expect(card).not.toBeNull();
  const buttons = within(card as HTMLElement).getAllByRole("button");
  fireEvent.click(buttons[buttons.length - 1]);
}

describe.each(["grid", "list"] as const)("Make a copy (%s view)", (viewMode) => {
  afterEach(() => {
    toast.remove();
    useUIStore.setState({ viewMode: "grid" });
  });

  it("copies the document, toasts and shows the copy at the top", async () => {
    useUIStore.setState({ viewMode });
    const original = doc("doc-1", "Quarterly plan", "final draft");
    const other = doc("doc-2", "Older notes");
    const copy = doc("doc-3", "Copy of Quarterly plan", "final draft");
    let copied = false;
    const copyCalls: string[] = [];
    server.use(
      http.get(`${API}/documents`, () =>
        HttpResponse.json({
          items: copied ? [copy, original, other] : [original, other],
          total: copied ? 3 : 2,
          page: 1,
          size: 50,
          pages: 1,
        })
      ),
      http.post(`${API}/documents/:id/copy`, ({ params }) => {
        copyCalls.push(params.id as string);
        copied = true;
        return HttpResponse.json(copy, { status: 201 });
      })
    );

    renderPage();
    await openMenuFor("Quarterly plan");
    fireEvent.click(screen.getByRole("button", { name: "Make a copy" }));

    expect(await screen.findByText("Copy created")).toBeInTheDocument();
    expect(copyCalls).toEqual(["doc-1"]);
    await waitFor(() =>
      expect(documentTitles()).toEqual(["Copy of Quarterly plan", "Quarterly plan", "Older notes"])
    );
    expect(screen.queryByRole("button", { name: "Make a copy" })).not.toBeInTheDocument();
  });

  it("shows the API error message when the copy fails", async () => {
    useUIStore.setState({ viewMode });
    server.use(
      http.get(`${API}/documents`, () =>
        HttpResponse.json({ items: [doc("doc-1", "Quarterly plan")], total: 1, page: 1, size: 50, pages: 1 })
      ),
      http.post(`${API}/documents/:id/copy`, () =>
        HttpResponse.json({ detail: "Document not found" }, { status: 404 })
      )
    );

    renderPage();
    await openMenuFor("Quarterly plan");
    fireEvent.click(screen.getByRole("button", { name: "Make a copy" }));

    expect(await screen.findByText("Document not found")).toBeInTheDocument();
    expect(screen.queryByText("Copy created")).not.toBeInTheDocument();
    expect(documentTitles()).toEqual(["Quarterly plan"]);
  });
});
