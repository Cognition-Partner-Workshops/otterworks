import { Given, When, Then } from "@cucumber/cucumber";
import { expect } from "@playwright/test";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { uniqueEmail } from "../../e2e/fixtures/test-helpers";
import { OtterWorld } from "../support/world";

const BASE_URL = process.env.BASE_URL || "http://localhost:3000";
const GATEWAY_URL = process.env.GATEWAY_URL || "http://localhost:8080/api/v1";
const fixtureDir = path.resolve(__dirname, "../../e2e/fixtures/preview");

async function uploadFixture(
  world: OtterWorld,
  filename: string,
  mimeType: string,
  uploadName = filename,
) {
  let token = world.parameters.token as string | undefined;
  if (!token) {
    await world.page.goto(`${BASE_URL}/register`);
    await world.page.getByLabel("Full name").fill("Preview Account");
    await world.page.getByLabel("Email").fill(uniqueEmail());
    await world.page.getByLabel("Password", { exact: true }).fill("Passw0rd!23");
    await world.page.getByLabel("Confirm password").fill("Passw0rd!23");
    await world.page.getByRole("button", { name: "Create account" }).click();
    await expect(world.page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
    token = await world.page.evaluate(() => localStorage.getItem("otter_access_token")) ?? undefined;
    world.parameters.token = token;
  }
  if (!token) throw new Error("Registration did not produce an access token");
  const buffer = await readFile(path.join(fixtureDir, filename));
  const response = await world.page.request.post(`${GATEWAY_URL}/files/upload`, {
    headers: { Authorization: `Bearer ${token}` },
    multipart: { file: { name: uploadName, mimeType, buffer } },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  world.parameters.fileId = body.file?.id ?? body.id;
}

Given("I have uploaded a preview text file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.txt", "text/plain");
});

Given("I have uploaded a preview Markdown file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.md", "text/markdown");
});

Given("I have uploaded a preview image", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.png", "image/png");
});

Given("I have uploaded a preview audio file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.wav", "audio/wav");
});

Given("I have uploaded a preview video file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.webm", "video/webm");
});

Given("I have uploaded a preview PDF file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.pdf", "application/pdf");
});

Given("I have uploaded a preview CSV file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.csv", "text/csv");
});

Given("I have uploaded a corrupt preview DOCX file", async function (this: OtterWorld) {
  await uploadFixture(this, "corrupt.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document");
});

Given("I have uploaded a preview image whose first storage request fails", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.png", "image/png");
  this.parameters.storageRequests = 0;
  this.parameters.downloadUrlCalls = 0;
  this.page.on("request", (request) => {
    if (request.url().includes(`/files/${this.parameters.fileId}/download`)) {
      this.parameters.downloadUrlCalls += 1;
    }
  });
  let storageRequests = 0;
  await this.page.route("http://localhost:4566/otterworks-files/**", async (route) => {
    storageRequests += 1;
    this.parameters.storageRequests = storageRequests;
    if (storageRequests === 1) await route.fulfill({ status: 403, body: "Expired" });
    else await route.continue();
  });
});

Given("I have uploaded a preview ZIP file", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.zip", "application/zip");
});

Given("I have uploaded a preview unknown binary", async function (this: OtterWorld) {
  await uploadFixture(this, "preview.bin", "application/octet-stream");
});

When("I open the file from the Files list", async function (this: OtterWorld) {
  await this.page.goto(`${BASE_URL}/files`);
  await this.page.getByText("preview.txt", { exact: true }).first().click();
});

When("I choose Preview from the Files list", async function (this: OtterWorld) {
  await this.page.goto(`${BASE_URL}/files`);
  await this.page.locator("button:has(svg.lucide-ellipsis-vertical)").first().click();
  await this.page.getByRole("button", { name: "Preview" }).click();
});

When("I open its detail route", async function (this: OtterWorld) {
  this.page.on("request", (request) => {
    if (request.headers().range === "bytes=0-499999") this.parameters.previewRangeSeen = true;
  });
  await this.page.goto(`${BASE_URL}/files/${this.parameters.fileId}`);
});

Then("the inline preview shows its text without downloading", async function (this: OtterWorld) {
  await expect(this.page.locator("[data-testid='line-numbered-text']")).toContainText("Inline preview fixture");
});

Then("the Markdown heading and Rendered toggle are shown", async function (this: OtterWorld) {
  await expect(this.page.getByRole("heading", { name: "Preview fixture" })).toBeVisible();
  await expect(this.page.getByRole("button", { name: "Rendered" })).toBeVisible();
});

Then("the image is shown inline", async function (this: OtterWorld) {
  await expect(this.page.locator(".bg-gray-50 img[src*='otterworks-files']").first()).toBeVisible();
});

Then("native audio controls are shown", async function (this: OtterWorld) {
  await expect(this.page.locator("audio[controls][preload='metadata']")).toBeVisible();
});

Then("native video controls are shown", async function (this: OtterWorld) {
  await expect(this.page.locator("video[controls]")).toBeVisible();
});

Then("the PDF frame and safe new-tab link are shown", async function (this: OtterWorld) {
  await expect(this.page.locator("iframe[title='preview.pdf']")).toBeVisible();
  await expect(this.page.getByRole("link", { name: "Open in new tab" })).toHaveAttribute("rel", "noopener noreferrer");
});

Then("the first CSV row is shown as headers", async function (this: OtterWorld) {
  await expect(this.page.getByRole("columnheader", { name: "File" })).toBeVisible();
});

Then("the image is shown inline after a URL refresh", async function (this: OtterWorld) {
  const image = this.page.locator(".bg-gray-50 img[src*='otterworks-files']").first();
  await expect.poll(() => image.evaluate((element: HTMLImageElement) => element.naturalWidth)).toBeGreaterThan(0);
  expect(this.parameters.storageRequests).toBeGreaterThanOrEqual(2);
  expect(this.parameters.downloadUrlCalls).toBeGreaterThanOrEqual(2);
});

Then("the preview error and recovery actions are shown", async function (this: OtterWorld) {
  await expect(this.page.getByText("Could not load preview")).toBeVisible();
  await expect(this.page.getByRole("button", { name: "Retry" })).toBeVisible();
  await expect(this.page.getByRole("alert").getByRole("button", { name: "Download" })).toBeVisible();
});

Then("the archive entry is listed without extraction", async function (this: OtterWorld) {
  await expect(this.page.getByText("preview.txt")).toBeVisible();
});

Then("the unsupported type message and Download button are shown", async function (this: OtterWorld) {
  await expect(this.page.getByText("Preview isn't available for this file type")).toBeVisible();
  await expect(this.page.getByRole("button", { name: "Download" }).last()).toBeVisible();
});

Then("its content is loaded with a byte range", async function (this: OtterWorld) {
  await expect(this.page.locator("[data-testid='line-numbered-text']")).toContainText("Inline preview fixture");
  await expect.poll(() => this.parameters.previewRangeSeen).toBe(true);
});
