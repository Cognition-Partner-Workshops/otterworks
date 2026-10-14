import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  login: vi.fn(),
  register: vi.fn(),
  getProfile: vi.fn(),
  logout: vi.fn(),
}));
vi.mock("@/lib/api", () => ({ authApi: api }));

import LoginPage from "@/pages/login";
import RegisterPage from "@/pages/register";
import { AuthProvider } from "@/providers/auth-provider";
import { useAuthStore } from "@/stores/auth-store";

const user = { id: "u-1", email: "qa@example.test", displayName: "QA User" };

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/dashboard" element={<h1>Dashboard</h1>} />
      </Routes>
    </MemoryRouter>
  );
}

function fillLogin(email: string, password: string) {
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: email } });
  fireEvent.change(screen.getByLabelText("Password"), { target: { value: password } });
  fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
}

function fillRegister(v: { name: string; email: string; pw: string; confirm: string }) {
  fireEvent.change(screen.getByLabelText("Full name"), { target: { value: v.name } });
  fireEvent.change(screen.getByLabelText("Email"), { target: { value: v.email } });
  fireEvent.change(screen.getByLabelText("Password", { exact: true }), { target: { value: v.pw } });
  fireEvent.change(screen.getByLabelText("Confirm password"), { target: { value: v.confirm } });
  fireEvent.click(screen.getByRole("button", { name: /create account/i }));
}

beforeEach(() => {
  Object.values(api).forEach((fn) => fn.mockReset());
  localStorage.clear();
  useAuthStore.setState({ user: null, isAuthenticated: false, isLoading: true });
});

describe("LoginPage (QA)", () => {
  it("stores tokens, sets the user and navigates to /dashboard on success", async () => {
    api.login.mockResolvedValue({ accessToken: "acc", refreshToken: "ref", expiresAt: 0 });
    api.getProfile.mockResolvedValue(user);
    renderAt("/login");
    fillLogin("qa@example.test", "Passw0rd!23");
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(api.login).toHaveBeenCalledWith({ email: "qa@example.test", password: "Passw0rd!23" });
    expect(localStorage.getItem("otter_access_token")).toBe("acc");
    expect(localStorage.getItem("otter_refresh_token")).toBe("ref");
    expect(useAuthStore.getState().isAuthenticated).toBe(true);
  });

  it("shows a generic error and stays on /login for bad credentials", async () => {
    api.login.mockRejectedValue(new Error("401"));
    renderAt("/login");
    fillLogin("qa@example.test", "wrong");
    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
    expect(localStorage.getItem("otter_access_token")).toBeNull();
    expect(screen.queryByRole("heading", { name: "Dashboard" })).toBeNull();
  });

  it("validates email format client-side without calling the API", async () => {
    renderAt("/login");
    fillLogin("not-an-email", "x");
    await waitFor(() => expect(api.login).not.toHaveBeenCalled());
  });

  it("requires a password", async () => {
    renderAt("/login");
    fillLogin("qa@example.test", "");
    expect(await screen.findByText("Password is required")).toBeInTheDocument();
    expect(api.login).not.toHaveBeenCalled();
  });

  it("toggles password visibility", () => {
    renderAt("/login");
    const pw = screen.getByLabelText("Password") as HTMLInputElement;
    expect(pw.type).toBe("password");
    const toggle = pw.parentElement!.querySelector("button")!;
    fireEvent.click(toggle);
    expect(pw.type).toBe("text");
  });

  it("does not leave a token behind when the profile fetch fails after login", async () => {
    api.login.mockResolvedValue({ accessToken: "acc", refreshToken: "ref", expiresAt: 0 });
    api.getProfile.mockRejectedValue(new Error("profile 500"));
    renderAt("/login");
    fillLogin("qa@example.test", "Passw0rd!23");
    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});

describe("RegisterPage (QA)", () => {
  it("registers, stores tokens and navigates to /dashboard", async () => {
    api.register.mockResolvedValue({ accessToken: "acc", refreshToken: "ref", expiresAt: 0 });
    api.getProfile.mockResolvedValue(user);
    renderAt("/register");
    fillRegister({ name: "QA User", email: "qa@example.test", pw: "Passw0rd!23", confirm: "Passw0rd!23" });
    expect(await screen.findByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(api.register).toHaveBeenCalledWith(
      expect.objectContaining({ displayName: "QA User", email: "qa@example.test", password: "Passw0rd!23" })
    );
    expect(localStorage.getItem("otter_access_token")).toBe("acc");
  });

  it("shows the duplicate-email error when the API rejects", async () => {
    api.register.mockRejectedValue(new Error("400"));
    renderAt("/register");
    fillRegister({ name: "QA User", email: "dup@example.test", pw: "Passw0rd!23", confirm: "Passw0rd!23" });
    expect(await screen.findByText(/registration failed/i)).toBeInTheDocument();
  });

  it.each([
    [{ name: "A", email: "qa@example.test", pw: "Passw0rd!23", confirm: "Passw0rd!23" }, "Name must be at least 2 characters"],
    [{ name: "QA User", email: "qa@example.test", pw: "short", confirm: "short" }, "Password must be at least 8 characters"],
    [{ name: "QA User", email: "qa@example.test", pw: "Passw0rd!23", confirm: "Different1!" }, "Passwords do not match"],
  ])("blocks submission on invalid input %#", async (values, message) => {
    renderAt("/register");
    fillRegister(values);
    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(api.register).not.toHaveBeenCalled();
  });
});

describe("AuthProvider (QA)", () => {
  it("resolves to unauthenticated immediately with no stored token", async () => {
    render(<AuthProvider><div>child</div></AuthProvider>);
    await waitFor(() => expect(useAuthStore.getState().isLoading).toBe(false));
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
    expect(api.getProfile).not.toHaveBeenCalled();
  });

  it("restores the session from a stored token on reload", async () => {
    localStorage.setItem("otter_access_token", "acc");
    api.getProfile.mockResolvedValue(user);
    render(<AuthProvider><div>child</div></AuthProvider>);
    await waitFor(() => expect(useAuthStore.getState().isAuthenticated).toBe(true));
    expect(useAuthStore.getState().user).toEqual(user);
  });

  it("drops to unauthenticated when the stored token is rejected", async () => {
    localStorage.setItem("otter_access_token", "expired");
    api.getProfile.mockRejectedValue(new Error("401"));
    render(<AuthProvider><div>child</div></AuthProvider>);
    await waitFor(() => expect(useAuthStore.getState().isLoading).toBe(false));
    expect(useAuthStore.getState().isAuthenticated).toBe(false);
  });
});
