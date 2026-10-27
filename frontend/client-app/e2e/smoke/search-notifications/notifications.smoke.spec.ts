import { test, expect } from "./search-notifications.fixtures";

test.describe("Notifications page (signed in)", () => {
  test(
    "a signed-in customer sees the notification for a file another customer shared with them",
    { tag: ["@smoke", "@smoke-notifications"] },
    async ({ page, customer, sharedFileNotification }) => {
      const main = page.getByRole("main");

      await test.step("open /notifications as the signed-in customer", async () => {
        await page.goto("/notifications");
        await expect(page.getByRole("heading", { name: "Notifications", exact: true })).toBeVisible();
        await expect(page.getByRole("banner").getByText(customer.displayName)).toBeVisible();
      });

      await test.step("the shared-file notification is listed as unread", async () => {
        await expect(main.getByText("1 unread notification", { exact: true })).toBeVisible();
        const notification = main.getByRole("button", { name: /File Shared With You/ });
        await expect(notification).toHaveCount(1);
        await expect(notification).toContainText(
          `A file has been shared with you by user ${sharedFileNotification.sharer.id}.`
        );
      });

      await test.step("the notification links to the shared file", async () => {
        await expect(
          main.getByRole("link", { name: /File Shared With You/ })
        ).toHaveAttribute("href", `/files/${sharedFileNotification.fileId}`);
      });
    }
  );
});
