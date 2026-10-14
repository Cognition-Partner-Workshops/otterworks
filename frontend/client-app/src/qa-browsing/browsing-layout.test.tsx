import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { Breadcrumb } from "@/components/layout/breadcrumb";
import { Sidebar } from "@/components/layout/sidebar";
import { useAuthStore } from "@/stores/auth-store";
import { useUIStore } from "@/stores/ui-store";

describe("browsing Breadcrumb", () => {
  it("renders an accessible nav whose home icon links to /dashboard", () => {
    render(
      <MemoryRouter>
        <Breadcrumb items={[]} />
      </MemoryRouter>
    );
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(within(nav).getByRole("link", { name: "Home" })).toHaveAttribute("href", "/dashboard");
  });

  it("renders intermediate items as links and the last item as plain text", () => {
    render(
      <MemoryRouter>
        <Breadcrumb items={[{ label: "Files", href: "/files" }, { label: "Reports" }]} />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute("href", "/files");
    expect(screen.getByText("Reports").closest("a")).toBeNull();
  });

  it("supports deeper trails", () => {
    render(
      <MemoryRouter>
        <Breadcrumb
          items={[
            { label: "Files", href: "/files" },
            { label: "Parent", href: "/files?folder=p" },
            { label: "Child" },
          ]}
        />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Parent" })).toHaveAttribute("href", "/files?folder=p");
    expect(screen.getAllByRole("link")).toHaveLength(3);
  });
});

describe("browsing Sidebar navigation", () => {
  beforeEach(() => {
    useUIStore.setState({ sidebarOpen: true });
    useAuthStore.setState({
      user: { id: "u1", email: "qa@example.test", displayName: "QA User" },
      isAuthenticated: true,
      isLoading: false,
    });
  });

  function renderAt(path: string) {
    return render(
      <MemoryRouter initialEntries={[path]}>
        <Sidebar />
      </MemoryRouter>
    );
  }

  const expected: Array<[string, string]> = [
    ["Dashboard", "/dashboard"],
    ["Recent", "/recent"],
    ["Files", "/files"],
    ["Documents", "/documents"],
    ["Search", "/search"],
    ["Shared with me", "/shared"],
    ["Starred", "/starred"],
    ["Notifications", "/notifications"],
    ["Trash", "/trash"],
    ["Settings", "/settings"],
  ];

  it.each(expected)("links %s to %s", (label, href) => {
    renderAt("/dashboard");
    const link = screen.getAllByRole("link").find((a) => a.textContent?.trim() === label);
    expect(link, `nav link ${label}`).toBeDefined();
    expect(link).toHaveAttribute("href", href);
  });

  function linkFor(label: string) {
    return screen.getAllByRole("link").find((a) => a.textContent?.trim() === label)!;
  }

  it("highlights the active route", () => {
    renderAt("/trash");
    expect(linkFor("Trash").className).not.toBe(linkFor("Files").className);
    expect(linkFor("Recent").className).toBe(linkFor("Files").className);
  });

  it("keeps Files active on a nested file deep link", () => {
    renderAt("/files/abc-123");
    expect(linkFor("Files").className).toBe(
      (() => {
        const other = render(
          <MemoryRouter initialEntries={["/files"]}>
            <Sidebar />
          </MemoryRouter>
        );
        const cls = within(other.container).getAllByRole("link").find((a) => a.textContent?.trim() === "Files")!.className;
        other.unmount();
        return cls;
      })()
    );
  });

  it("does not mark /files active for an unrelated prefix like /filesystem", () => {
    renderAt("/filesystem");
    expect(linkFor("Files").className).toBe(linkFor("Recent").className);
  });
});
