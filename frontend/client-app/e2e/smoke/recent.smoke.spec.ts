import { test, expect } from "../fixtures/fixtures";

test("recent lists a document edited today under Today", {
  tag: ["@smoke", "@page-recent"],
  annotation: { type: "route", description: "/recent" },
}, async ({ page, document }) => {
  await page.goto("/recent");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { level: 1, name: "Recent" })).toBeVisible();
  await expect(main.getByRole("heading", { level: 2, name: "Today" })).toBeVisible();
  await expect(main.getByRole("link", { name: document.title })).toHaveAttribute(
    "href",
    `/documents/${document.id}`,
  );
});
