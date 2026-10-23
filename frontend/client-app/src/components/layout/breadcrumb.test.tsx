import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { Breadcrumb } from "./breadcrumb";

function renderCrumbs(items: Parameters<typeof Breadcrumb>[0]["items"]) {
  return render(
    <MemoryRouter>
      <Breadcrumb items={items} />
    </MemoryRouter>
  );
}

describe("Breadcrumb", () => {
  it("is exposed as a navigation landmark labelled Breadcrumb", () => {
    renderCrumbs([]);
    expect(screen.getByRole("navigation", { name: "Breadcrumb" })).toBeInTheDocument();
  });

  it("always starts with a Home link to the dashboard", () => {
    renderCrumbs([{ label: "Files", href: "/files" }]);
    expect(screen.getByRole("link", { name: "Home" })).toHaveAttribute("href", "/dashboard");
  });

  it("renders linked ancestors and an unlinked current item", () => {
    renderCrumbs([
      { label: "Files", href: "/files" },
      { label: "Quarterly reports" },
    ]);
    expect(screen.getByRole("link", { name: "Files" })).toHaveAttribute("href", "/files");
    const current = screen.getByText("Quarterly reports");
    expect(current.closest("a")).toBeNull();
  });

  it("keeps items in the given order", () => {
    renderCrumbs([
      { label: "Files", href: "/files" },
      { label: "Parent", href: "/files?folder=p" },
      { label: "Child" },
    ]);
    const nav = screen.getByRole("navigation", { name: "Breadcrumb" });
    expect(nav.textContent).toBe("FilesParentChild");
  });

  it("renders only the Home link when there are no items", () => {
    renderCrumbs([]);
    expect(screen.getAllByRole("link")).toHaveLength(1);
  });
});
