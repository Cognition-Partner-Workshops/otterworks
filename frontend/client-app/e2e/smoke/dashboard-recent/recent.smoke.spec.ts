import { expect, test } from "./dashboard-recent.fixtures";

test.use({ trace: "retain-on-failure", screenshot: "only-on-failure" });

test(
  "recent lists the signed-in customer's new file and document under Today, newest first",
  {
    tag: ["@smoke", "@smoke-dashboard-recent"],
  },
  async ({ page, customer, customerDocument, customerFile, runId }) => {
    const main = page.getByRole("main");

    await test.step("Open /recent as the signed-in customer", async () => {
      await page.goto("/recent");
      await expect(
        main.getByRole("heading", { level: 1, name: "Recent", exact: true }),
      ).toBeVisible();
      await expect(page.getByText(customer.email, { exact: true })).toBeVisible();
    });

    await test.step("Group both new records under Today only", async () => {
      await expect(
        main.getByRole("heading", { level: 2, name: "Today", exact: true }),
      ).toBeVisible();
      await expect(
        main.getByRole("heading", { level: 2, name: "Yesterday", exact: true }),
      ).toHaveCount(0);
      await expect(
        main.getByRole("heading", { level: 2, name: "This week", exact: true }),
      ).toHaveCount(0);
      await expect(
        main.getByRole("heading", { level: 2, name: "Earlier", exact: true }),
      ).toHaveCount(0);
    });

    await test.step("List the file before the document", async () => {
      const items = main.getByRole("link").filter({ hasText: runId });
      await expect(items).toHaveCount(2);
      await expect(items).toContainText([
        customerFile.name,
        customerDocument.title,
      ]);
    });

    await test.step("Open each listed record at its own route", async () => {
      await expect(
        main.getByRole("link", { name: customerFile.name }),
      ).toHaveAttribute("href", `/files/${customerFile.id}`);
      await expect(
        main.getByRole("link", { name: customerDocument.title }),
      ).toHaveAttribute("href", `/documents/${customerDocument.id}`);
    });
  },
);

test(
  "recent shows the empty state for a brand-new customer",
  {
    tag: ["@smoke", "@smoke-dashboard-recent"],
  },
  async ({ page, customer }) => {
    const main = page.getByRole("main");

    await test.step("Open /recent as the new customer", async () => {
      await page.goto("/recent");
      await expect(
        main.getByRole("heading", { level: 1, name: "Recent", exact: true }),
      ).toBeVisible();
      await expect(page.getByText(customer.email, { exact: true })).toBeVisible();
    });

    await test.step("Show no recent items or date groups", async () => {
      await expect(main.getByText("No recent items", { exact: true })).toBeVisible();
      await expect(
        main.getByRole("heading", { level: 2, name: "Today", exact: true }),
      ).toHaveCount(0);
    });
  },
);
