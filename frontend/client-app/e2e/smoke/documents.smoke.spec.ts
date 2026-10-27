import { test, expect } from "./documents.fixtures";

test("documents page lists the signed-in customer's documents", {
  tag: ["@smoke", "@page-documents"],
  annotation: { type: "route", description: "/documents" },
}, async ({ page, seededDocument }) => {
  await page.goto("/documents");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();
  await expect(main.getByRole("link", { name: seededDocument.title })).toHaveAttribute(
    "href",
    `/documents/${seededDocument.id}`,
  );
});
