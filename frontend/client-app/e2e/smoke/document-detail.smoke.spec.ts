import { test, expect } from "../fixtures/signed-in";

test("signed-in customer opening /documents/:id sees that document's title and saved content", async ({
  customerPage,
  customerDocument,
}) => {
  const main = customerPage.getByRole("main");

  await test.step("Open the customer's document", async () => {
    await customerPage.goto(`/documents/${customerDocument.id}`);
  });

  await test.step("The title and saved content are visible", async () => {
    await expect(
      main.getByRole("heading", {
        name: customerDocument.title,
        level: 1,
      })
    ).toBeVisible();
    await expect(
      customerPage
        .getByRole("navigation", { name: "Breadcrumb" })
        .getByText(customerDocument.title)
    ).toBeVisible();
    await expect(main.getByText(customerDocument.bodyText)).toBeVisible();
  });
});
