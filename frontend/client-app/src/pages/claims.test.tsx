import { render, screen, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import ClaimsPage, { claimStatus } from "./claims";

vi.mock("@/components/layout/app-shell", () => ({
  AppShell: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));
afterEach(cleanup);

function show(path: string) {
  render(<MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/claims" element={<ClaimsPage />} />
    <Route path="/claims/:id" element={<ClaimsPage />} />
  </Routes></MemoryRouter>);
}

describe("claims register", () => {
  it("lists every status and links to details", () => {
    show("/claims");
    Object.values(claimStatus).forEach((label) => expect(screen.getByText(label)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Claim 1" })).toHaveAttribute("href", "/claims/1");
  });
  it("shows a claim detail", () => {
    show("/claims/5");
    expect(screen.getByText(claimStatus[5])).toBeInTheDocument();
    expect(screen.getByText("55.00")).toBeInTheDocument();
  });
  it("handles an absent claim", () => {
    show("/claims/999");
    expect(screen.getByRole("alert")).toHaveTextContent("Claim not found");
  });
});
