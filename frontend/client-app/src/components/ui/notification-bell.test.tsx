import { http, HttpResponse } from "msw";
import { screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it } from "vitest";
import { NotificationBell } from "./notification-bell";
import { billingServer } from "../../test-setup";
import { API, renderAt, resetStores } from "@/test/browsing-helpers";

function mockUnread(count: number | null, status = 200) {
  billingServer.use(
    http.get(`${API}/notifications/unread-count`, () =>
      status === 200
        ? HttpResponse.json({ count })
        : HttpResponse.json({ error: "bad request" }, { status })
    )
  );
}

describe("NotificationBell", () => {
  beforeEach(() => resetStores());

  it("links to the notifications page", async () => {
    mockUnread(0);
    renderAt(<NotificationBell />);
    expect(await screen.findByRole("link", { name: "Notifications" })).toHaveAttribute(
      "href",
      "/notifications"
    );
  });

  it("shows no badge when there are no unread notifications", async () => {
    mockUnread(0);
    const { container } = renderAt(<NotificationBell />);
    await screen.findByRole("link", { name: "Notifications" });
    expect(container.querySelector(".bg-red-500")).toBeNull();
  });

  it("shows the unread count badge and accessible label", async () => {
    mockUnread(3);
    renderAt(<NotificationBell />);
    expect(
      await screen.findByRole("link", { name: "Notifications (3 unread)" })
    ).toHaveTextContent("3");
  });

  it("caps the badge at 99+", async () => {
    mockUnread(150);
    renderAt(<NotificationBell />);
    expect(
      await screen.findByRole("link", { name: "Notifications (150 unread)" })
    ).toHaveTextContent("99+");
  });

  it("degrades to a plain bell when the unread-count call fails", async () => {
    mockUnread(null, 400);
    const { container } = renderAt(<NotificationBell />);
    await waitFor(() =>
      expect(screen.getByRole("link", { name: "Notifications" })).toBeInTheDocument()
    );
    expect(container.querySelector(".bg-red-500")).toBeNull();
  });
});
