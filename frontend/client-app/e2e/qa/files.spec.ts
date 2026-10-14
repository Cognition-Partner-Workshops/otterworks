import { test, expect, type Page, type Locator, type APIRequestContext } from "@playwright/test";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const GATEWAY = process.env.API_GATEWAY_URL || "http://localhost:8080";
const PASSWORD = "OtterworksTest123!";

async function registerViaApi(request: APIRequestContext) {
  const email = `qa-files-${Date.now()}-${Math.random().toString(36).slice(2, 7)}@otterworks.test`;
  const res = await request.post(`${GATEWAY}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, displayName: "QA Files" },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return { email, accessToken: body.accessToken as string, refreshToken: body.refreshToken as string };
}

async function signIn(page: Page, request: APIRequestContext) {
  const user = await registerViaApi(request);
  await page.addInitScript(([a, r]) => {
    localStorage.setItem("otter_access_token", a);
    localStorage.setItem("otter_refresh_token", r);
  }, [user.accessToken, user.refreshToken]);
  await page.goto("/files");
  await expect(page.getByRole("heading", { name: /Files|My Files/i })).toBeVisible({ timeout: 15_000 });
  return user;
}

async function uploadViaPicker(page: Page, name: string, content: string, mimeType = "text/plain"): Promise<string> {
  await page.getByRole("button", { name: /^Upload$/ }).first().click();
  const uploaded = page.waitForResponse((r) => r.url().includes("/files/upload") && r.request().method() === "POST");
  await page.locator('input[type="file"]').last().setInputFiles({ name, mimeType, buffer: Buffer.from(content) });
  const response = await uploaded;
  expect(response.status()).toBe(201);
  const fileId = (await response.json()).file.id as string;
  await expect(fileCard(page, name)).toBeVisible({ timeout: 10_000 });
  return fileId;
}

function fileCard(page: Page, name: string): Locator {
  return page.locator("div.group").filter({ has: page.getByRole("link", { name: new RegExp(name) }) }).first();
}

async function openCardMenu(card: Locator) {
  await card.hover();
  await card.locator("button:not([aria-label])").first().click();
}

test.describe("QA: files", () => {
  test("picker upload lists the file and detail page previews its text", async ({ page, request }) => {
    await signIn(page, request);
    const name = `picker-${Date.now()}.txt`;
    await uploadViaPicker(page, name, "hello from the picker\nsecond line");

    await fileCard(page, name).getByRole("link").first().click();
    await expect(page).toHaveURL(/\/files\/[0-9a-f-]{36}$/);
    await expect(page.getByRole("heading", { name })).toBeVisible();
    const inline = page.getByText("hello from the picker");
    const framed = page.frameLocator('iframe[title^="Preview of"]').getByText("hello from the picker");
    await expect
      .poll(async () => (await inline.isVisible()) || (await framed.isVisible().catch(() => false)), { timeout: 10_000 })
      .toBe(true);
  });

  test("drag-and-drop onto the files page uploads the file", async ({ page, request }) => {
    await signIn(page, request);
    const name = `dropped-${Date.now()}.txt`;
    const dataTransfer = await page.evaluateHandle((fileName) => {
      const dt = new DataTransfer();
      dt.items.add(new File(["dropped content"], fileName, { type: "text/plain" }));
      return dt;
    }, name);
    const uploaded = page.waitForResponse((r) => r.url().includes("/files/upload") && r.request().method() === "POST");
    const root = page.locator('[role="presentation"]').first();
    await root.dispatchEvent("dragenter", { dataTransfer });
    await root.dispatchEvent("drop", { dataTransfer });
    expect((await uploaded).status()).toBe(201);
    await expect(fileCard(page, name)).toBeVisible({ timeout: 10_000 });
  });

  test("star and unstar persist across reload and show on Starred", async ({ page, request }) => {
    await signIn(page, request);
    const name = `star-${Date.now()}.txt`;
    await uploadViaPicker(page, name, "star me");

    await fileCard(page, name).getByRole("button", { name: "Star" }).click();
    await page.reload();
    await expect(fileCard(page, name).getByRole("button", { name: "Unstar" })).toBeVisible();
    await page.goto("/starred");
    await expect(page.getByText(name)).toBeVisible({ timeout: 10_000 });

    await page.goto("/files");
    await fileCard(page, name).getByRole("button", { name: "Unstar" }).click();
    await page.reload();
    await expect(fileCard(page, name).getByRole("button", { name: "Star" })).toBeVisible();
  });

  test("rename via card menu updates the listing", async ({ page, request }) => {
    await signIn(page, request);
    const name = `rename-${Date.now()}.txt`;
    const renamed = name.replace("rename-", "renamed-");
    await uploadViaPicker(page, name, "rename me");

    const card = fileCard(page, name);
    await openCardMenu(card);
    await page.getByRole("button", { name: /Rename/ }).click();
    const input = page.locator("main").getByRole("textbox");
    await input.fill(renamed);
    await input.press("Enter");
    await expect(page.getByText("File renamed")).toBeVisible();
    await expect(fileCard(page, renamed)).toBeVisible();
    await page.reload();
    await expect(fileCard(page, renamed)).toBeVisible();
  });

  test("download keeps the user in the app and the presigned URL serves the uploaded bytes", async ({ page, request }) => {
    const user = await signIn(page, request);
    const name = `download-${Date.now()}.txt`;
    const content = "download round trip";
    const fileId = await uploadViaPicker(page, name, content);

    const urlRes = await request.get(`${GATEWAY}/api/v1/files/${fileId}/download`, {
      headers: { Authorization: `Bearer ${user.accessToken}` },
    });
    expect(urlRes.status()).toBe(200);
    const object = await request.get(String((await urlRes.json()).url).replace("://localstack:", "://localhost:"));
    expect(object.status()).toBe(200);
    expect(await object.text()).toBe(content);

    const downloadEvent = page.waitForEvent("download", { timeout: 5_000 }).catch(() => null);
    await openCardMenu(fileCard(page, name));
    await page.getByRole("button", { name: /Download/ }).click();
    const download = await downloadEvent;
    expect(page.url(), "clicking Download should not navigate away from the files page").toMatch(/\/files$/);
    expect(download, "clicking Download should save a file").not.toBeNull();
    expect(download!.suggestedFilename()).toBe(name);
  });

  test("card menu offers a Move action", async ({ page, request }) => {
    await signIn(page, request);
    const name = `move-${Date.now()}.txt`;
    await uploadViaPicker(page, name, "move me");
    await openCardMenu(fileCard(page, name));
    await expect(page.getByRole("button", { name: /Move/ })).toBeVisible({ timeout: 3_000 });
  });

  test("delete moves the file to Trash", async ({ page, request }) => {
    await signIn(page, request);
    const name = `delete-${Date.now()}.txt`;
    await uploadViaPicker(page, name, "delete me");

    await openCardMenu(fileCard(page, name));
    await page.getByRole("button", { name: /Delete/ }).click();
    await expect(page.getByText("File moved to trash")).toBeVisible();
    await expect(fileCard(page, name)).toHaveCount(0);
    await page.goto("/trash");
    await expect(page.getByText(name)).toBeVisible({ timeout: 10_000 });
  });

  test("files over the advertised 100MB limit are rejected client-side", async ({ page, request }) => {
    test.setTimeout(120_000);
    await signIn(page, request);
    const dir = mkdtempSync(join(tmpdir(), "qa-files-"));
    const bigPath = join(dir, "too-big.bin");
    writeFileSync(bigPath, Buffer.alloc(100 * 1024 * 1024 + 1));

    let uploadAttempted = false;
    page.on("request", (r) => {
      if (r.url().includes("/files/upload")) uploadAttempted = true;
    });
    await page.getByRole("button", { name: /^Upload$/ }).first().click();
    await page.locator('input[type="file"]').last().setInputFiles(bigPath);
    await expect(page.getByText(/too large|exceeds|larger than|100 ?MB/i).last()).toBeVisible();
    await page.waitForTimeout(1_000);
    expect(uploadAttempted, "oversized file should not be sent to the server").toBe(false);
  });
});
