import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import LoginPage from "./login";
import RegisterPage from "./register";

describe.each([
  { Page: LoginPage, heading: "Sign in to your account", submit: "Sign in" },
  { Page: RegisterPage, heading: "Create your account", submit: "Create account" },
])("$heading accessibility", ({ Page, heading, submit }) => {
  function renderPage() {
    render(<MemoryRouter><Page /></MemoryRouter>);
  }

  it("has a main landmark and a visible level-one heading", () => {
    renderPage();
    expect(screen.getByRole("main")).toContainElement(
      screen.getByRole("heading", { level: 1, name: heading })
    );
  });

  it("names the password toggle and updates its action when clicked", () => {
    renderPage();
    const password = screen.getByLabelText("Password", { exact: true });
    expect(password).toHaveAttribute("type", "password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle).toHaveAttribute("aria-controls", password.id);
    fireEvent.click(toggle);
    expect(password).toHaveAttribute("type", "text");
    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(password).toHaveAttribute("type", "password");
  });

  it("associates invalid fields with their visible validation messages", async () => {
    renderPage();
    fireEvent.click(screen.getByRole("button", { name: submit }));
    const email = screen.getByLabelText("Email");
    await waitFor(() => expect(email).toHaveAttribute("aria-invalid", "true"));
    expect(email).toHaveAccessibleDescription("Please enter a valid email");
    const password = screen.getByLabelText("Password", { exact: true });
    expect(password).toHaveAttribute("aria-invalid", "true");
    expect(password).toHaveAccessibleDescription(
      Page === LoginPage ? "Password is required" : "Password must be at least 8 characters"
    );
    if (Page === RegisterPage) {
      expect(screen.getByLabelText("Full name")).toHaveAccessibleDescription("Name must be at least 2 characters");
      expect(screen.getByLabelText("Confirm password")).toHaveAccessibleDescription("Please confirm your password");
    }
  });
});

it("names the confirm-password toggle independently", () => {
  render(<MemoryRouter><RegisterPage /></MemoryRouter>);
  const confirm = screen.getByLabelText("Confirm password");
  const toggle = screen.getByRole("button", { name: "Show confirm password" });
  expect(toggle).toHaveAttribute("aria-controls", confirm.id);
  fireEvent.click(toggle);
  expect(confirm).toHaveAttribute("type", "text");
  fireEvent.click(screen.getByRole("button", { name: "Hide confirm password" }));
  expect(confirm).toHaveAttribute("type", "password");
  expect(screen.getByLabelText("Password", { exact: true })).toHaveAttribute("type", "password");
});
