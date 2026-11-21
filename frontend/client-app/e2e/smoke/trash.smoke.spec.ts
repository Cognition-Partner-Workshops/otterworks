import { test, expect } from "../fixtures/fixtures";

// own customer: trash rows have no role, so Restore can't be scoped to one item, and the seed checks the whole trash list
test.use({ freshCustomer: true });

test(
  "trash lists the file the customer deleted, ready to restore",
  { tag: ["@smoke", "@page-trash"], annotation: { type: "route", description: "/trash" } },
  async ({ page, trashedFile }) => {
    await page.goto("/trash");
    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { name: "Trash", level: 1 })).toBeVisible();
    // a11y gap: trash rows are plain divs, the file name is an unlabelled <p> with no role
    await expect(main.getByText(trashedFile.name, { exact: true })).toBeVisible();
    await expect(main.getByRole("button", { name: "Restore" })).toBeVisible();
  },
);
