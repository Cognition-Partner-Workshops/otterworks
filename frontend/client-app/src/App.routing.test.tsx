import { http, HttpResponse } from "msw";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import App from "./App";
import { billingServer } from "./test-setup";
import { API } from "@/test/browsing-helpers";

function renderApp(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
    </MemoryRouter>
  );
}

describe("App routing (deep links and 404)", () => {
  beforeEach(() => {
    localStorage.clear();
    billingServer.use(
      http.get(`${API}/*`, () => HttpResponse.json({ error: "unauthorized" }, { status: 401 }))
    );
  });

  it("renders the landing page at /", async () => {
    renderApp("/");
    expect(await screen.findByRole("heading", { name: /^OtterWorks$/ })).toBeInTheDocument();
  });

  it.each(["/does-not-exist", "/files/abc/extra/segments", "/settings/unknown", "/DASHBOARDX"])(
    "renders the 404 page for unknown path %s",
    async (path) => {
      renderApp(path);
      expect(await screen.findByRole("heading", { name: /404/ })).toBeInTheDocument();
      expect(screen.getByRole("link", { name: "Back to home" })).toHaveAttribute("href", "/");
    }
  );

  it("404 Back to home returns to the landing page", async () => {
    renderApp("/nope");
    fireEvent.click(await screen.findByRole("link", { name: "Back to home" }));
    expect(await screen.findByRole("heading", { name: /^OtterWorks$/ })).toBeInTheDocument();
  });

  it.each([
    ["/terms", "Terms of Service"],
    ["/privacy", "Privacy Policy"],
    ["/login", "Sign in to your account"],
    ["/register", "Create your account"],
  ])("deep link %s renders its page directly", async (path, text) => {
    renderApp(path);
    expect(await screen.findByText(text)).toBeInTheDocument();
  });

  it.each([
    ["/dashboard", "Dashboard"],
    ["/recent", "Recent"],
    ["/settings", "Settings"],
    ["/notifications", "Notifications"],
  ])("deep link %s mounts the app shell route", async (path, heading) => {
    localStorage.setItem("otter_access_token", "test-token");
    billingServer.use(
      http.get(`${API}/auth/profile`, () =>
        HttpResponse.json({ id: "u1", email: "o@otterworks.test", displayName: "Olive Otter" })
      ),
      http.get(`${API}/notifications/unread-count`, () => HttpResponse.json({ count: 0 })),
      http.get(`${API}/*`, () => HttpResponse.json({}))
    );
    renderApp(path);
    expect(await screen.findByRole("heading", { name: heading, level: 1 })).toBeInTheDocument();
  });
});
