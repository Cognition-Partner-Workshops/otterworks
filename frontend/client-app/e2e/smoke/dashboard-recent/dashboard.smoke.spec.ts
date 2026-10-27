import { expect, test } from "./dashboard-recent.fixtures";

test.use({ trace: "retain-on-failure", screenshot: "only-on-failure" });

test(
  "dashboard lists the signed-in customer's new document, file and upload activity",
  {
    tag: ["@smoke", "@smoke-dashboard-recent"],
  },
  async ({ page, customer, customerDocument, customerFile }) => {
    const main = page.getByRole("main");

    await test.step("Open /dashboard as the signed-in customer", async () => {
      await page.goto("/dashboard");
      await expect(
        main.getByRole("heading", {
          level: 1,
          name: "Dashboard",
          exact: true,
        }),
      ).toBeVisible();
      await expect(page.getByText(customer.email, { exact: true })).toBeVisible();
    });

    await test.step("Show the customer's new document", async () => {
      await expect(
        main.getByRole("link", { name: customerDocument.title }),
      ).toHaveAttribute("href", `/documents/${customerDocument.id}`);
    });

    await test.step("Show the customer's new file", async () => {
      await expect(
        main.getByRole("link", { name: customerFile.name }),
      ).toHaveAttribute("href", `/files/${customerFile.id}`);
    });

    await test.step("Count only this customer's file and document", async () => {
      // Standard exception: stat cards have no role or accessible name; anchor on the label and step up to the card.
      await expect(
        main.getByText("Total files", { exact: true }).locator(".."),
      ).toHaveText(/^1\s*Total files$/);
      await expect(
        main.getByText("Documents", { exact: true }).locator(".."),
      ).toHaveText(/^1\s*Documents$/);
    });

    await test.step("Show the upload in recent activity", async () => {
      await expect(
        main.getByText(`Uploaded ${customerFile.name}`),
      ).toBeVisible();
    });
  },
);
