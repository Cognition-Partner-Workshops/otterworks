import { test, expect, type APIRequestContext, type Page } from "@playwright/test";
import { expectDashboard, loginUser, uniqueEmail } from "./fixtures/test-helpers";

const PASSWORD = "Passw0rd!23";
const DEFECT = {
  type: "defect",
  description:
    "A signed-in user's HS512 access token was not decoded by document-service: " +
    "POST /api/v1/documents answered 401 \"owner_id is required\" and GET /api/v1/documents lost its owner filter",
};

async function signInAsFreshUser(page: Page, request: APIRequestContext) {
  const email = uniqueEmail();

  await test.step("Register a fresh account through the auth API", async () => {
    const response = await request.post("/api/v1/auth/register", {
      data: { email, password: PASSWORD, displayName: "Create Doc User" },
    });
    expect(response.status()).toBe(201);
  });

  await test.step("Sign in through the login form", async () => {
    await loginUser(page, email, PASSWORD);
    await expectDashboard(page);
  });
}

async function pressAndExpectCreated(page: Page, buttonName: string) {
  const created = page.waitForResponse(
    (r) => r.request().method() === "POST" && new URL(r.url()).pathname === "/api/v1/documents"
  );
  await page.getByRole("button", { name: buttonName }).click();
  const response = await created;
  expect(response.status(), `POST /api/v1/documents -> ${await response.text()}`).toBe(201);
}

async function expectEditorForNewDocument(page: Page) {
  await expect(page).toHaveURL(/\/documents\/[0-9a-f-]{36}$/);
  await expect(page.getByRole("heading", { name: "Untitled document" })).toBeVisible();
}

test.describe("Create document", () => {
  test(
    "signed-in user creates a document with New document",
    { tag: ["@defect-doc-create-owner-id", "@documents"], annotation: DEFECT },
    async ({ page, request }) => {
      await signInAsFreshUser(page, request);

      await test.step("Open Documents", async () => {
        await page.getByRole("link", { name: "Documents" }).click();
        await expect(page.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();
      });

      await test.step("Press New document", async () => {
        await pressAndExpectCreated(page, "New document");
      });

      await test.step("Land in the editor for the new document", async () => {
        await expectEditorForNewDocument(page);
      });
    }
  );

  test(
    "fresh user sees only their own (empty) documents and creates one with Create document",
    { tag: ["@defect-doc-create-owner-id", "@documents"], annotation: DEFECT },
    async ({ page, request }) => {
      await signInAsFreshUser(page, request);

      await test.step("Open Documents and see the empty state", async () => {
        await page.getByRole("link", { name: "Documents" }).click();
        await expect(page.getByRole("heading", { name: "Documents", level: 1 })).toBeVisible();
        await expect(page.getByRole("heading", { name: "No documents yet" })).toBeVisible();
      });

      await test.step("Press Create document", async () => {
        await pressAndExpectCreated(page, "Create document");
      });

      await test.step("Land in the editor for the new document", async () => {
        await expectEditorForNewDocument(page);
      });
    }
  );
});
