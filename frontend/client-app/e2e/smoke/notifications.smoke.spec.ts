import { test, expect } from "./notifications.fixtures";

test("notifications page lists a notification received by the signed-in customer", {
  tag: ["@smoke", "@page-notifications"],
  annotation: { type: "route", description: "/notifications" },
}, async ({ page, sharedFileNotification: { sharerId, fileId } }) => {
  await page.goto("/notifications");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Notifications", level: 1 })).toBeVisible();
  const notification = main.getByRole("link", { name: new RegExp(`File Shared With You.*${sharerId}`) });
  await expect(notification).toHaveAttribute("href", `/files/${fileId}`);
  await expect(main.getByText("1 unread notification")).toBeVisible(); // count is a plain <p>, no role
});
