import { test, expect } from "./documents.fixtures";

test("signed-in customer sees their own document listed on /documents", async ({
  customerPage,
  customerDocument,
}) => {
  const main = customerPage.getByRole("main");

  await test.step("Open /documents as the signed-in customer", async () => {
    await customerPage.goto("/documents");
    await expect(
      main.getByRole("heading", { name: "Documents", level: 1 })
    ).toBeVisible();
  });

  await test.step("The customer's document is listed and links to its page", async () => {
    const documentLink = main.getByRole("link", {
      name: customerDocument.title,
    });

    await expect(documentLink).toBeVisible();
    await expect(documentLink).toHaveAttribute(
      "href",
      `/documents/${customerDocument.id}`
    );
  });
});
