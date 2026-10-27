import { randomUUID } from "node:crypto";
import { test, expect } from "./smoke/documents/documents.fixtures";

test.describe("Documents page (signed in)", () => {
  test("New document creates an Untitled document and opens it", async ({
    customerPage,
  }) => {
    const main = customerPage.getByRole("main");

    await test.step("Open /documents as the signed-in customer", async () => {
      await customerPage.goto("/documents");
      await expect(
        main.getByRole("heading", { name: "Documents", level: 1 })
      ).toBeVisible();
    });

    await test.step("Create a new document", async () => {
      await main.getByRole("button", { name: "New document" }).click();
    });

    await test.step("The Untitled document opens", async () => {
      await expect(customerPage).toHaveURL(/\/documents\/[0-9a-f-]{36}$/);
      await expect(
        main.getByRole("heading", {
          name: "Untitled document",
          level: 1,
        })
      ).toBeVisible();
    });
  });

  test("filter narrows the list to the matching document", async ({
    customerPage,
    createDocument,
  }) => {
    const main = customerPage.getByRole("main");
    const { alpha, beta } = await test.step(
      "Create matching and non-matching documents",
      async () => ({
        alpha: await createDocument("Smoke alpha"),
        beta: await createDocument("Smoke beta"),
      })
    );

    await test.step("Open /documents and confirm both documents are listed", async () => {
      await customerPage.goto("/documents");
      await expect(
        main.getByRole("link", { name: alpha.title })
      ).toBeVisible();
      await expect(main.getByRole("link", { name: beta.title })).toBeVisible();
    });

    await test.step("Filter to the matching document", async () => {
      await main
        .getByPlaceholder("Filter documents...")
        .fill(alpha.title);
      await expect(
        main.getByRole("link", { name: alpha.title })
      ).toBeVisible();
      await expect(
        main.getByRole("link", { name: beta.title })
      ).toHaveCount(0);
    });

    await test.step("Show the no-matches state for an unknown query", async () => {
      await main
        .getByPlaceholder("Filter documents...")
        .fill(`no-match-${randomUUID()}`);
      await expect(main.getByText("No matching documents")).toBeVisible();
    });
  });

  test("list view shows the document as a row with its word count", async ({
    customerPage,
    customerDocument,
  }) => {
    const main = customerPage.getByRole("main");
    const documentLink = main.getByRole("link", {
      name: customerDocument.title,
    });

    await test.step("Open /documents in grid view and verify the content preview", async () => {
      await customerPage.goto("/documents");
      await expect(documentLink).toContainText(customerDocument.bodyText);
    });

    await test.step("Switch to list view and verify its word count", async () => {
      await main.getByRole("button", { name: "New document" }).focus();
      // Standard exception: the icon-only grid/list controls have no accessible names, so use keyboard navigation from the named New document button.
      await customerPage.keyboard.press("Tab");
      await customerPage.keyboard.press("Tab");
      await customerPage.keyboard.press("Enter");

      await expect(documentLink).not.toContainText(customerDocument.bodyText);
      await expect(documentLink).toContainText(
        `${customerDocument.wordCount} words`
      );
    });
  });

  test("a customer with no documents sees the empty state", async ({
    customerPage,
  }) => {
    const main = customerPage.getByRole("main");

    await test.step("Open /documents with a new customer", async () => {
      await customerPage.goto("/documents");
    });

    await test.step("The empty state offers to create a document", async () => {
      await expect(main.getByText("No documents yet")).toBeVisible();
      await expect(
        main.getByRole("button", { name: "Create document" })
      ).toBeVisible();
    });
  });

  test("document page breadcrumb leads back to the Documents list", async ({
    customerPage,
    customerDocument,
  }) => {
    const main = customerPage.getByRole("main");

    await test.step("Open the customer's document", async () => {
      await customerPage.goto(`/documents/${customerDocument.id}`);
    });

    await test.step("Return to the Documents list from the breadcrumb", async () => {
      await customerPage
        .getByRole("navigation", { name: "Breadcrumb" })
        .getByRole("link", { name: "Documents" })
        .click();
    });

    await test.step("The Documents list shows the customer's document", async () => {
      await expect(customerPage).toHaveURL(/\/documents$/);
      await expect(
        main.getByRole("heading", { name: "Documents", level: 1 })
      ).toBeVisible();
      await expect(
        main.getByRole("link", { name: customerDocument.title })
      ).toBeVisible();
    });
  });
});

test.describe("Documents page (signed out)", () => {
  test("signed-out visitor opening /documents is sent to sign in", async ({
    page,
  }) => {
    await test.step("Open /documents without a customer session", async () => {
      await page.goto("/documents");
    });

    await test.step("The visitor is redirected to sign in", async () => {
      await expect(page).toHaveURL(/\/login$/);
      await expect(page.getByText("Sign in to your account")).toBeVisible();
    });
  });
});
