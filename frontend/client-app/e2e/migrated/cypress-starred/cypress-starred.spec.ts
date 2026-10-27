import { test, expect, legacy } from "./fixtures";

test(
  "CY-starred-01 shows a saved document",
  {
    tag: ["@CY-starred-01", "@cypress-starred"],
    annotation: { type: "cypress", description: `${legacy.spec}#shows a saved document` },
  },
  async ({ page, SavedDocument }) => {
    const main = page.getByRole("main");
    const card = main.getByRole("link", { name: new RegExp(SavedDocument.Title) });

    await test.step("CY-starred-01-STEP-01 Star document Quarterly Planning", async () => {
      await page.goto("/documents");
      await card.getByRole("button", { name: "Star", exact: true }).click();
      await expect(card.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
      await expect
        .poll(() => page.evaluate(() => JSON.parse(localStorage.getItem("otter_starred_items") ?? "{}")))
        .toHaveProperty([`${SavedDocument.UserId}:${SavedDocument.DocumentId}`, "itemType"], "document");
    });

    const documentResponse = page.waitForResponse(
      (response) =>
        response.request().method() === "GET" &&
        new URL(response.url()).pathname === `/api/v1/documents/${SavedDocument.DocumentId}`,
    );

    await test.step("CY-starred-01-STEP-02 Visit /starred", async () => {
      await page.goto("/starred");
      await expect(main.getByRole("heading", { name: "Starred", exact: true, level: 1 })).toBeVisible();
    });

    await test.step("CY-starred-01-STEP-03 Wait document request", async () => {
      const response = await documentResponse;
      expect(response.status()).toBe(200);
      expect(await response.json()).toMatchObject({ id: SavedDocument.DocumentId, title: SavedDocument.Title });
    });

    await test.step("CY-starred-01-STEP-04 Verify Quarterly Planning is visible", async () => {
      await expect(main.getByRole("heading", { name: "Documents", exact: true, level: 2 })).toBeVisible();
      await expect(card).toBeVisible();
      await expect(card).toHaveAttribute("href", `/documents/${SavedDocument.DocumentId}`);
      await expect(card.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
    });
  },
);
