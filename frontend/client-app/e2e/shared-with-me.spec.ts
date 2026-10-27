import { test, expect } from "./fixtures/api-setup";

test("recipient opens a file another user shared with them", {
  tag: ["@sharing", "@api-seeded"],
}, async ({ page, sharedFile }, testInfo) => {
  const { file, recipient } = sharedFile;
  const main = page.getByRole("main");

  await test.step("Recipient finds the shared file", async () => {
    await page.goto("/shared");
    await expect(main.getByRole("heading", { name: "Shared with me", exact: true })).toBeVisible();
    await expect(main.getByRole("link", { name: file.name })).toBeVisible();
    await expect(main.getByRole("heading", { name: "Nothing shared with you yet" })).not.toBeVisible();
  });

  await test.step("Recipient opens the shared file detail", async () => {
    await main.getByRole("link", { name: file.name }).click();
    await expect(page).toHaveURL(`/files/${file.id}`);
    await expect(main.getByRole("heading", { name: file.name, exact: true })).toBeVisible();
    await expect(main.getByRole("button", { name: "Download", exact: true })).toBeVisible();
    await expect(main.getByRole("heading", { name: "Shared with", exact: true })).toBeVisible();
    // The sharing entry is a plain paragraph without an accessible role or label.
    await expect(main.getByText(`${recipient.email} · view`, { exact: true })).toBeVisible();
    await testInfo.attach("recipient-file-detail", {
      body: await page.screenshot({ fullPage: true }), contentType: "image/png",
    });
  });
});
