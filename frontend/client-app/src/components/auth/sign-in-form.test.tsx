import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { SignInForm } from "./sign-in-form";

vi.mock("@/lib/api", () => ({
  authApi: {
    login: vi.fn(),
    getProfile: vi.fn(),
  },
}));

function renderForm(idPrefix = "") {
  return render(
    <MemoryRouter initialEntries={["/login"]}>
      <Routes>
        <Route path="/login" element={<SignInForm idPrefix={idPrefix} />} />
        <Route path="/dashboard" element={<div>Dashboard route</div>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("SignInForm", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    localStorage.clear();
    useAuthStore.getState().setUser(null);
    vi.mocked(authApi.login).mockResolvedValue({
      accessToken: "a",
      refreshToken: "r",
      expiresAt: 0,
    });
    vi.mocked(authApi.getProfile).mockResolvedValue({
      id: "user-1",
      email: "user@example.com",
      displayName: "Demo User",
    });
  });

  it("logs in and navigates to the dashboard when submitted by clicking", async () => {
    renderForm();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "secret" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith({
        email: "user@example.com",
        password: "secret",
      });
    });
    expect(await screen.findByText("Dashboard route")).toBeInTheDocument();
    expect(localStorage.getItem("otter_access_token")).toBe("a");
    expect(localStorage.getItem("otter_refresh_token")).toBe("r");
  });

  it("submits when Enter is pressed in the password field", async () => {
    renderForm();
    const password = screen.getByLabelText("Password");
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(password, { target: { value: "secret" } });
    fireEvent.keyDown(password, { key: "Enter", code: "Enter" });
    fireEvent.submit(password.closest("form")!);

    await waitFor(() => {
      expect(authApi.login).toHaveBeenCalledWith({
        email: "user@example.com",
        password: "secret",
      });
    });
    expect(await screen.findByText("Dashboard route")).toBeInTheDocument();
  });

  it("shows a login error without navigating when authentication is rejected", async () => {
    vi.mocked(authApi.login).mockRejectedValueOnce(new Error("Unauthorized"));
    renderForm();
    fireEvent.change(screen.getByLabelText("Email"), {
      target: { value: "user@example.com" },
    });
    fireEvent.change(screen.getByLabelText("Password"), {
      target: { value: "wrong" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));

    expect(
      await screen.findByText("Invalid email or password. Please try again."),
    ).toBeInTheDocument();
    expect(screen.queryByText("Dashboard route")).not.toBeInTheDocument();
  });

  it("prefixes the input IDs for a landing-page form", () => {
    renderForm("landing-");

    expect(screen.getByLabelText("Email")).toHaveAttribute(
      "id",
      "landing-email",
    );
    expect(screen.getByLabelText("Password")).toHaveAttribute(
      "id",
      "landing-password",
    );
  });
});
