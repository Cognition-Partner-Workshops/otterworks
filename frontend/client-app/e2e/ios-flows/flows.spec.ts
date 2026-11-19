import { test, expect, type Page } from "@playwright/test";

test.describe.configure({ mode: "default" });
async function navigate(page: Page, name: string) {
  const link = page.locator("aside").getByRole("link", { name, exact: true });
  if (!(await link.isVisible())) await page.getByRole("button", { name: "Open menu" }).click();
  await link.click();
  await page.getByRole("button", { name: "Toggle sidebar" }).click();
}
async function login(page: Page, password = "HarborPass123!") {
  await page.goto("/login");
  await page.getByLabel("Email", { exact: true }).fill("tester@example.com");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  if (password === "HarborPass123!") await expect(page).toHaveURL(/dashboard/);
}
test.beforeEach(async ({ request }) => {
  await request.post("http://127.0.0.1:4010/__reset");
});

test("bad password is rejected", async ({ page }) => {
  await login(page, "wrong-password");
  await expect(page.getByText("Invalid email or password. Please try again.")).toBeVisible();
  await expect(page).toHaveURL(/login/);
});

test("login and sidebar pages", async ({ page }) => {
  await login(page);
  await expect(page.getByText("Harbor report.txt").first()).toBeVisible();
  for (const name of ["Recent", "Files", "Documents", "Search", "Margins", "Shared with me", "Starred", "Notifications", "Trash", "Settings", "Dashboard"]) {
    await navigate(page, name);
    await expect(page.getByRole("heading", { name, exact: true }).first()).toBeVisible();
  }
});

test("files list, upload, detail and download", async ({ page }) => {
  await login(page);
  await navigate(page, "Files");
  await expect(page.getByText("Voyages", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Upload", exact: true }).click();
  await page.locator('input[type="file"]').setInputFiles({ name: "deck-log.txt", mimeType: "text/plain", buffer: Buffer.from("Deck log") });
  await expect(page.getByText("deck-log.txt").first()).toBeVisible();
  await page.getByText("Harbor report.txt", { exact: true }).dblclick();
  await expect(page.getByRole("heading", { name: "Harbor report.txt" })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download", exact: true }).first().click();
  expect((await download).suggestedFilename()).toBe("Harbor report.txt");
});

test("document edits persist without a collaboration service", async ({ page, request }) => {
  await login(page);
  await navigate(page, "Documents");
  await page.getByText("Voyage notes", { exact: true }).click();
  const editor = page.locator('[contenteditable="true"]');
  await expect(editor).toContainText("Welcome aboard");
  await editor.fill("Edited harbor voyage");
  await page.getByRole("button", { name: "Save", exact: true }).click();
  await expect.poll(async () => (await (await request.get("http://127.0.0.1:4010/api/v1/documents/doc-1", { headers: { Authorization: "Bearer mock" } })).json()).content).toContain("Edited harbor voyage");
});

test("search results and empty results", async ({ page }) => {
  await login(page);
  await navigate(page, "Search");
  const search = page.getByPlaceholder("Search files, documents, and folders...");
  await search.fill("Harbor");
  await search.press("Enter");
  await expect(page.getByText("Harbor report.txt", { exact: true })).toBeVisible();
  await search.fill("nonexistent-fixture");
  await search.press("Enter");
  await expect(page.getByText(/No results/).first()).toBeVisible();
});

test("settings profile persists", async ({ page }) => {
  await login(page);
  await navigate(page, "Settings");
  await expect(page.getByLabel("Full name")).toHaveValue("Harbor Tester");
  await page.getByLabel("Full name").fill("Harbor Captain");
  await page.getByRole("button", { name: "Save changes" }).click();
  await expect(page.getByText("Profile updated successfully.")).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Full name")).toHaveValue("Harbor Captain");
});

test("notifications and margins CSV", async ({ page }) => {
  await login(page);
  await navigate(page, "Notifications");
  await expect(page.getByText("Your voyage report is ready")).toBeVisible();
  await navigate(page, "Margins");
  await expect(page.getByText("HARBOR-01", { exact: true })).toBeVisible();
  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export CSV" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.csv$/);
});
