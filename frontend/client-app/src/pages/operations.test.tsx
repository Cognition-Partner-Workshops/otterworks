import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import OperationsPage from "./operations";
import { apiClient } from "@/lib/api-client";
import { useAuthStore } from "@/stores/auth-store";

vi.mock("@/lib/api-client", () => ({ apiClient: { get: vi.fn(), post: vi.fn(), delete: vi.fn() } }));
vi.mock("@/components/layout/app-shell", () => ({ AppShell: ({ children }: { children: React.ReactNode }) => <div>{children}</div> }));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<MemoryRouter><QueryClientProvider client={queryClient}><OperationsPage /></QueryClientProvider></MemoryRouter>);
}

beforeEach(() => {
  vi.resetAllMocks();
  localStorage.clear();
  useAuthStore.setState({ isAuthenticated: true, isLoading: false });
  vi.mocked(apiClient.get).mockResolvedValue({ data: { incidents: [] } });
  vi.mocked(apiClient.post).mockResolvedValue({ data: {} });
  vi.mocked(apiClient.delete).mockResolvedValue({ data: {} });
});
afterEach(cleanup);

describe("Operations Console", () => {
  it("renders scenarios and empty incidents, persists chaos and resets it", async () => {
    localStorage.setItem("ow_admin_chaos_state", "invalid json");
    renderPage();
    expect(await screen.findByText("No incidents reported.")).toBeInTheDocument();
    for (const scenario of ["Break Search Autocomplete", "Break File Uploads", "Break Notification Queue", "Inject Query Latency"]) {
      expect(screen.getByRole("button", { name: scenario })).toBeInTheDocument();
    }
    expect(screen.getByRole("heading", { name: "Search Service" })).toBeInTheDocument();
    expect(screen.getByText(/Autocomplete suggest endpoint crashes/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Break Search Autocomplete" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/admin/chaos", { service: "search-service", scenario: "suggest_500" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Break Search Autocomplete" })).toHaveAttribute("aria-pressed", "true"));
    expect(screen.getByText("Chaos active — Grafana alert fires in ~30s")).toBeInTheDocument();
    expect(JSON.parse(localStorage.getItem("ow_admin_chaos_state")!)).toEqual({ "search-service": true });
    fireEvent.click(screen.getByRole("button", { name: "Reset all" }));
    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/admin/chaos"));
    await waitFor(() => expect(screen.getByRole("button", { name: "Break Search Autocomplete" })).toHaveAttribute("aria-pressed", "false"));
    expect(screen.queryByText("Chaos active — Grafana alert fires in ~30s")).not.toBeInTheDocument();
  });

  it("shows request errors without marking failed chaos active", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new Error("Forbidden"));
    vi.mocked(apiClient.post).mockRejectedValue(new Error("Forbidden"));
    renderPage();
    expect(await screen.findByText("Failed to load incidents.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Break File Uploads" }));
    expect(await screen.findByText(/Operation failed/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Break File Uploads" })).toHaveAttribute("aria-pressed", "false");
  });

  it("shows session details and launches sessions for active incidents without one", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ data: { incidents: [
      { id: "1", title: "Search unavailable", severity: "high", status: "investigating", active: true, devinSessionId: "session", devinSessionStatus: "running", devinSessionUrl: "https://app.devin.ai/sessions/session" },
      { id: "2", title: "Upload failed", severity: "critical", status: "open", active: true },
      { id: "3", title: "Old incident", severity: "low", status: "closed", active: false },
    ] } });
    renderPage();
    expect(await screen.findByText("Search unavailable")).toBeInTheDocument();
    expect(screen.getByText("Devin session: running")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "View Devin session" })).toHaveAttribute("href", "https://app.devin.ai/sessions/session");
    expect(screen.getAllByRole("button", { name: "Launch Devin" })).toHaveLength(1);
    fireEvent.click(screen.getByRole("button", { name: "Launch Devin" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/admin/incidents/2/trigger_session", {}));
  });

  it("creates incidents with the Angular service payload", async () => {
    renderPage();
    fireEvent.change(screen.getByLabelText("Title"), { target: { value: "Search failed" } });
    fireEvent.change(screen.getByLabelText("Description"), { target: { value: "Suggestions return errors" } });
    fireEvent.change(screen.getByLabelText("Affected service"), { target: { value: "search-service" } });
    fireEvent.click(screen.getByRole("button", { name: "Create incident" }));
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledWith("/admin/incidents", { incident: { title: "Search failed", description: "Suggestions return errors", severity: "high", affected_service: "search-service" } }));
    await waitFor(() => expect(screen.getByLabelText("Title")).toHaveValue(""));
  });

  it("does not fetch administrative data for signed-out users", () => {
    useAuthStore.setState({ isAuthenticated: false });
    renderPage();
    expect(apiClient.get).not.toHaveBeenCalled();
    expect(screen.queryByRole("button", { name: "Break Search Autocomplete" })).not.toBeInTheDocument();
  });
});
