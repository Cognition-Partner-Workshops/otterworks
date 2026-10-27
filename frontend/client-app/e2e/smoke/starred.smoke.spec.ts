import { test, expect } from "../fixtures/fixtures";

test("starred page lists the customer's starred document", {
  tag: ["@smoke", "@page-starred"],
  annotation: { type: "route", description: "/starred" },
}, async ({ page, starredDocument }) => {
  await page.goto("/starred");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Starred", level: 1 })).toBeVisible();
  await expect(main.getByRole("heading", { name: "Documents", level: 2 })).toBeVisible();
  await expect(main.getByRole("link", { name: starredDocument.title })).toHaveAttribute("href", `/documents/${starredDocument.id}`);
});
