import { test, expect } from "../fixtures/fixtures";

test("files page lists the signed-in customer's uploaded file", {
  tag: ["@smoke", "@page-files"],
  annotation: { type: "route", description: "/files" },
}, async ({ page, textFile }) => {
  await page.goto("/files");

  const main = page.getByRole("main");
  await expect(main.getByRole("heading", { name: "Files", level: 1 })).toBeVisible();
  await expect(main.getByRole("link", { name: textFile.name })).toBeVisible();
});
