import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar } from "./sidebar";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";
import { resetStores, testUser } from "@/test/browsing-helpers";

function renderSidebar(path = "/dashboard") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Sidebar />
    </MemoryRouter>
  );
}

const expectedLinks: Array<[string, string]> = [
  ["Dashboard", "/dashboard"],
  ["Recent", "/recent"],
  ["Files", "/files"],
  ["Documents", "/documents"],
  ["Search", "/search"],
  ["Margins", "/margins"],
  ["Shared with me", "/shared"],
  ["Starred", "/starred"],
  ["Notifications", "/notifications"],
  ["Trash", "/trash"],
  ["Settings", "/settings"],
];

describe("Sidebar", () => {
  beforeEach(() => resetStores());

  it("renders the Workspace, Collaboration and System groups", () => {
    renderSidebar();
    for (const group of ["Workspace", "Collaboration", "System"]) {
      expect(screen.getByText(group)).toBeInTheDocument();
    }
  });

  it.each(expectedLinks)("links %s to %s", (label, href) => {
    renderSidebar();
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: label })).toHaveAttribute("href", href);
  });

  it("highlights only the link for the current route", () => {
    renderSidebar("/settings");
    const nav = screen.getByRole("navigation");
    const active = within(nav)
      .getAllByRole("link")
      .filter((a) => a.className.includes("border-accent-500"));
    expect(active).toHaveLength(1);
    expect(active[0]).toHaveTextContent("Settings");
  });

  it("keeps the parent section active on a nested deep link", () => {
    renderSidebar("/documents/abc-123");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Documents" }).className).toContain(
      "border-accent-500"
    );
  });

  it("does not mark a section active for a route that only shares a prefix", () => {
    renderSidebar("/filesystem");
    const nav = screen.getByRole("navigation");
    expect(within(nav).getByRole("link", { name: "Files" }).className).not.toContain(
      "border-accent-500"
    );
  });

  it("has a brand link and a New button", () => {
    renderSidebar();
    expect(screen.getByRole("link", { name: /OtterWorks/ })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByRole("link", { name: "New" })).toHaveAttribute("href", "/files");
  });

  it("collapses to icons only when toggled and expands again", () => {
    renderSidebar();
    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(useUIStore.getState().sidebarOpen).toBe(false);
    expect(screen.queryByText("Workspace")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "New" })).not.toBeInTheDocument();
    // links stay navigable while collapsed
    expect(screen.getAllByRole("link").length).toBeGreaterThanOrEqual(expectedLinks.length);
    fireEvent.click(screen.getByRole("button", { name: "Toggle sidebar" }));
    expect(useUIStore.getState().sidebarOpen).toBe(true);
    expect(screen.getByText("Workspace")).toBeInTheDocument();
  });

  it("shows the signed-in user with initials and email", () => {
    renderSidebar();
    expect(screen.getByText(testUser.displayName)).toBeInTheDocument();
    expect(screen.getByText(testUser.email)).toBeInTheDocument();
    expect(screen.getByText("OO")).toBeInTheDocument();
  });

  it("hides the profile block when signed out", () => {
    resetStores(null);
    renderSidebar();
    expect(screen.queryByRole("button", { name: "Sign out" })).not.toBeInTheDocument();
  });

  it("calls logout from the Sign out button", () => {
    const logout = vi.fn();
    useAuthStore.setState({ logout });
    renderSidebar();
    fireEvent.click(screen.getByRole("button", { name: "Sign out" }));
    expect(logout).toHaveBeenCalledOnce();
  });
});
