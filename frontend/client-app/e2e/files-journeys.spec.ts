import { test, expect, type Page } from "@playwright/test";
import { registerUser, expectDashboard } from "./fixtures/test-helpers";

/**
 * Files-area QA journeys: folders, upload, rename, download, trash/restore.
 * Requires the local stack (gateway + file-service + LocalStack) to be up.
 */

const API_BASE = process.env.OTTERWORKS_API_BASE_URL ?? "http://localhost:8080";

function uniqueName(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

async function signUpAndOpenFiles(page: Page) {
  await registerUser(page, { name: "Files QA" });
  await expectDashboard(page);
  await page.goto("/files");
  await expect(page.getByRole("heading", { name: /Files|My Files/i })).toBeVisible({ timeout: 15_000 });
}

async function uploadViaUi(page: Page, fileName: string, body = "files e2e content") {
  await page.getByRole("button", { name: /^Upload$/ }).click();
  await page.locator('input[type="file"]').setInputFiles({
    name: fileName,
    mimeType: "text/plain",
    buffer: Buffer.from(body),
  });
  await expect(page.getByText(fileName).first()).toBeVisible({ timeout: 20_000 });
}

function itemCard(page: Page, name: string) {
  return page.locator(".group", { hasText: name }).last();
}

async function openItemMenu(page: Page, name: string) {
  const card = itemCard(page, name);
  await card.hover();
  await card.locator("button:not([aria-label])").last().click({ force: true });
}

async function accessToken(page: Page): Promise<string> {
  const token = await page.evaluate(() => localStorage.getItem("otter_access_token"));
  expect(token, "logged-in user should have an access token").toBeTruthy();
  return token as string;
}

test.describe("Files journeys", () => {
  test("create a folder and open it", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const folderName = uniqueName("QA Folder");
    await page.getByRole("button", { name: /New folder/i }).click();
    await page.getByPlaceholder("Folder name").fill(folderName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("Folder created")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(folderName).first()).toBeVisible();

    await page.getByText(folderName).first().click();
    await expect(page).toHaveURL(/folder=/, { timeout: 10_000 });
  });

  test("upload a file then rename it", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const fileName = `${uniqueName("upload")}.txt`;
    const renamed = `${uniqueName("renamed")}.txt`;
    await uploadViaUi(page, fileName);

    await page.goto("/files");
    await openItemMenu(page, fileName);
    await page.getByRole("button", { name: "Rename" }).click();
    const input = await page.locator(`input[value="${fileName}"]`).first().elementHandle();
    expect(input, "inline rename input should appear").toBeTruthy();
    await input!.fill(renamed);
    await input!.press("Enter");
    await expect(page.getByText("File renamed")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await expect(page.getByText(renamed).first()).toBeVisible({ timeout: 15_000 });
  });

  test("download serves the uploaded bytes", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const fileName = `${uniqueName("download")}.txt`;
    await uploadViaUi(page, fileName);
    await page.goto("/files");
    await openItemMenu(page, fileName);
    const blobResponse = page.context().waitForEvent("response", {
      predicate: (res) => res.url().includes("/otterworks-files/"),
      timeout: 15_000,
    });
    await page.getByRole("button", { name: "Download" }).click();
    const response = await blobResponse;
    expect(response.status()).toBe(200);
    expect(await response.text()).toBe("files e2e content");
  });

  // [REAL] handleDownload sets <a download> on a cross-origin presigned URL;
  // browsers ignore `download` cross-origin, so the SPA tab navigates to the
  // raw object instead of saving it.
  test("download keeps the user on the Files page", async ({ page, baseURL }) => {
    test.fail(true, "[REAL] Download navigates the tab to the raw S3 URL");
    await signUpAndOpenFiles(page);
    const fileName = `${uniqueName("stay")}.txt`;
    await uploadViaUi(page, fileName);
    await page.goto("/files");
    await openItemMenu(page, fileName);
    await page.getByRole("button", { name: "Download" }).click();
    await page.waitForTimeout(2_000);
    expect(new URL(page.url()).origin, "tab should stay on the web app").toBe(new URL(baseURL!).origin);
    await expect(page.getByText(`Downloading ${fileName}`)).toBeVisible({ timeout: 5_000 });
  });

  test("delete moves a file to trash and restore brings it back", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const fileName = `${uniqueName("trash")}.txt`;
    await uploadViaUi(page, fileName);
    await page.goto("/files");
    await openItemMenu(page, fileName);
    await page.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("File moved to trash")).toBeVisible({ timeout: 10_000 });

    await page.goto("/trash");
    await expect(page.getByText(fileName).first()).toBeVisible({ timeout: 15_000 });
    await page.getByRole("button", { name: "Restore" }).first().click();
    await expect(page.getByText("File restored")).toBeVisible({ timeout: 10_000 });

    await page.goto("/files");
    await expect(page.getByText(fileName).first()).toBeVisible({ timeout: 15_000 });
  });

  // [REAL] file-service list_files applies no folder filter when folder_id is
  // absent, so the root view shows files from every folder.
  test("root view does not show files that live inside a folder", async ({ page, request }) => {
    test.fail(true, "[REAL] root listing returns files from all folders");
    await signUpAndOpenFiles(page);
    const token = await accessToken(page);
    const headers = { Authorization: `Bearer ${token}` };
    const me = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString());

    const folderRes = await request.post(`${API_BASE}/api/v1/folders`, {
      headers,
      data: { name: uniqueName("Nested"), owner_id: me.sub },
    });
    expect(folderRes.status()).toBe(201);
    const folder = await folderRes.json();

    const nestedName = `${uniqueName("nested")}.txt`;
    const uploadRes = await request.post(`${API_BASE}/api/v1/files/upload`, {
      headers,
      multipart: {
        file: { name: nestedName, mimeType: "text/plain", buffer: Buffer.from("nested") },
        folder_id: folder.id,
      },
    });
    expect(uploadRes.status()).toBe(201);

    await page.goto(`/files?folder=${folder.id}`);
    await expect(page.getByText(nestedName).first()).toBeVisible({ timeout: 15_000 });

    await page.goto("/files");
    await expect(page.getByText(folder.name).first()).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(nestedName)).toHaveCount(0);
  });

  test("permanently delete a trashed file", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const fileName = `${uniqueName("purge")}.txt`;
    await uploadViaUi(page, fileName);
    await page.goto("/files");
    await openItemMenu(page, fileName);
    await page.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("File moved to trash")).toBeVisible({ timeout: 10_000 });

    await page.goto("/trash");
    await expect(page.getByText(fileName).first()).toBeVisible({ timeout: 15_000 });
    await page.getByTitle("Delete permanently").first().click();
    await page.getByRole("button", { name: "Delete permanently" }).click();
    await expect(page.getByText("File permanently deleted")).toBeVisible({ timeout: 10_000 });
    await expect(page.getByText(fileName)).toHaveCount(0);

    await page.goto("/files");
    await expect(page.getByRole("heading", { name: /Files|My Files/i })).toBeVisible();
    await expect(page.getByText(fileName)).toHaveCount(0);
  });

  test("rename and delete a folder", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const folderName = uniqueName("Rename Me");
    const renamed = uniqueName("Renamed Folder");
    await page.getByRole("button", { name: /New folder/i }).click();
    await page.getByPlaceholder("Folder name").fill(folderName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("Folder created")).toBeVisible({ timeout: 10_000 });

    await openItemMenu(page, folderName);
    await page.getByRole("button", { name: "Rename" }).click();
    const input = await page.locator(`input[value="${folderName}"]`).first().elementHandle();
    expect(input, "inline folder rename input should appear").toBeTruthy();
    await input!.fill(renamed);
    await input!.press("Enter");
    await expect(page.getByText("Folder renamed")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await expect(page.getByText(renamed).first()).toBeVisible({ timeout: 15_000 });

    await openItemMenu(page, renamed);
    await page.getByRole("button", { name: "Delete" }).click();
    await expect(page.getByText("Folder deleted")).toBeVisible({ timeout: 10_000 });
    await page.reload();
    await expect(page.getByRole("heading", { name: /Files|My Files/i })).toBeVisible({ timeout: 15_000 });
    await expect(page.getByText(renamed)).toHaveCount(0);
  });

  test("upload into a folder lists the file inside that folder", async ({ page }) => {
    await signUpAndOpenFiles(page);
    const folderName = uniqueName("Inbox");
    await page.getByRole("button", { name: /New folder/i }).click();
    await page.getByPlaceholder("Folder name").fill(folderName);
    await page.getByRole("button", { name: "Create" }).click();
    await expect(page.getByText("Folder created")).toBeVisible({ timeout: 10_000 });
    await page.getByText(folderName).first().click();
    await page.waitForURL((url) => url.searchParams.has("folder"), { timeout: 10_000 });

    const fileName = `${uniqueName("inside")}.txt`;
    await uploadViaUi(page, fileName);
    await page.reload();
    await expect(page.getByText(fileName).first()).toBeVisible({ timeout: 15_000 });
  });
});
