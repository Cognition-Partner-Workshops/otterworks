import { expect, test } from "../fixtures/signed-in";

test.use({ account: "fresh" });

test.use({ trace: "retain-on-failure", screenshot: "only-on-failure" });

test(
  "recent lists the signed-in customer's new file and document under Today, newest first",
  {
    tag: ["@smoke", "@smoke-dashboard-recent"],
  },
  async ({ page, customer, customerDocument, customerFile }) => {
    const main = page.getByRole("main");
    const frozenToday = new Date();
    frozenToday.setHours(12, 0, 0, 0);
    await page.clock.install({ time: frozenToday });

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
      const links = await main.getByRole("link").allTextContents();
      const fileIndex = links.findIndex((text) => text.includes(customerFile.name));
      const documentIndex = links.findIndex((text) => text.includes(customerDocument.title));
      expect(fileIndex).toBeGreaterThanOrEqual(0);
      expect(documentIndex).toBeGreaterThan(fileIndex);
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
