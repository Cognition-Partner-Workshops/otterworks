import { test, expect } from "../fixtures/fixtures";

test("documents page lists the signed-in customer's documents", {
  tag: ["@smoke", "@page-documents"],
  annotation: { type: "route", description: "/documents" },
}, async ({ page, document }) => {
  await page.goto("/documents");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();
  await expect(main.getByRole("link", { name: document.title })).toHaveAttribute(
    "href",
    `/documents/${document.id}`,
  );
});
