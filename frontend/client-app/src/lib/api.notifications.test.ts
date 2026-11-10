import { describe, it, expect } from "vitest";
import { http, HttpResponse } from "msw";
import { billingServer as server } from "../test-setup";
import { notificationsApi } from "./api";

// Response shapes as returned by notification-service (via the api-gateway).
describe("notificationsApi", () => {
  it("reads the unread count from the notification-service response", async () => {
    server.use(
      http.get("http://localhost:3000/api/v1/notifications/unread-count", () =>
        HttpResponse.json({ userId: "user-1", unreadCount: 4 })
      )
    );

    await expect(notificationsApi.getUnreadCount()).resolves.toBe(4);
  });

  it("sends page and pageSize when listing notifications", async () => {
    let query: URLSearchParams | undefined;
    server.use(
      http.get("http://localhost:3000/api/v1/notifications", ({ request }) => {
        query = new URL(request.url).searchParams;
        return HttpResponse.json({ data: [], total: 0, page: 1, pageSize: 20, hasMore: false });
      })
    );

    const result = await notificationsApi.list();

    expect(query?.get("page")).toBe("1");
    expect(query?.get("pageSize")).toBe("20");
    expect(result.pageSize).toBe(20);
  });
});
