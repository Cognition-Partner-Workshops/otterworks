import { test, expect } from "../fixtures/fixtures";

test(
  "shared: a signed-in customer sees a file another customer shared with them",
  { tag: ["@smoke", "@page-shared"], annotation: { type: "route", description: "/shared" } },
  async ({ page, sharedFile }) => {
    await page.goto("/shared");
    await expect(page.getByRole("heading", { name: "Shared with me", exact: true })).toBeVisible();
    await expect(page.getByRole("main").getByRole("link", { name: sharedFile.name })).toBeVisible();
  },
);
