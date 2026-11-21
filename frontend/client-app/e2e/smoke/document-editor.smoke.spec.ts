import { test, expect } from "../fixtures/fixtures";

test("document editor opens a saved document for editing", {
  tag: ["@smoke", "@page-document-editor"],
  annotation: { type: "route", description: "/documents/:id" },
}, async ({ page, document }) => {
  await page.goto(`/documents/${document.id}`);

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { level: 1, name: document.title })).toBeVisible();
  // a11y gap: the TipTap editing surface exposes no textbox role or name, so locate its saved paragraph by text.
  const savedContent = main.getByText(document.text, { exact: true });
  await expect(savedContent).toBeVisible();
  await expect(savedContent).toBeEditable();
});
