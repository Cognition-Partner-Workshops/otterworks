import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import TrashPage from "./trash";
import { filesApi } from "@/lib/api";
import type { FileItem } from "@/types";

vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

vi.mock("@/lib/api", () => ({
  filesApi: {
    getTrashed: vi.fn(),
    restore: vi.fn(),
    permanentDelete: vi.fn(),
  },
}));

const item = {
  id: "f1",
  name: "quarterly-report.txt",
  mimeType: "text/plain",
  size: 12,
  isFolder: false,
  trashedAt: new Date().toISOString(),
} as unknown as FileItem;

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <TrashPage />
    </QueryClientProvider>
  );
}

describe("Trash page", () => {
  beforeEach(() => {
    vi.mocked(filesApi.getTrashed).mockReset().mockResolvedValue({
      data: [item],
      total: 1,
      page: 1,
      pageSize: 50,
    } as never);
    vi.mocked(filesApi.permanentDelete).mockReset().mockResolvedValue(undefined);
  });

  it("asks for confirmation naming the file before permanently deleting", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));

    const dialog = screen.getByRole("alertdialog", { name: "Delete permanently?" });
    expect(dialog).toHaveTextContent("quarterly-report.txt");
    expect(filesApi.permanentDelete).not.toHaveBeenCalled();

    fireEvent.click(within(dialog).getByRole("button", { name: "Delete permanently" }));
    await waitFor(() => expect(filesApi.permanentDelete).toHaveBeenCalled());
    expect(vi.mocked(filesApi.permanentDelete).mock.calls[0][0]).toBe("f1");
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("does not delete when the confirmation is cancelled", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(filesApi.permanentDelete).not.toHaveBeenCalled();
  });

  it("confirms Empty trash with the item count", async () => {
    renderPage();
    fireEvent.click(await screen.findByRole("button", { name: /Empty Trash/ }));
    const dialog = screen.getByRole("alertdialog", { name: "Empty trash?" });
    expect(dialog).toHaveTextContent("all 1 item in trash");
    fireEvent.keyDown(document, { key: "Escape" });
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
    expect(filesApi.permanentDelete).not.toHaveBeenCalled();
  });
});
