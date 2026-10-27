import { test, expect, type APIRequestContext } from "@playwright/test";
import { uniqueEmail } from "../fixtures/test-helpers";

// Defect repro: a signed-in user presses "New document" and nothing happens.
// The documents API answers 401 "owner_id is required" even though the request
// carries a valid access token. Runs against the real stack (Vite -> API gateway
// -> auth-service / document-service); nothing is mocked.

test.use({ trace: "retain-on-failure", screenshot: "on" });

async function registerAccount(request: APIRequestContext) {
  const account = {
    displayName: "Owner Repro",
    email: uniqueEmail(),
    password: "Passw0rd!23",
  };
  const response = await request.post("/api/v1/auth/register", { data: account });
  expect(response.status(), await response.text()).toBe(201);
  return account;
}

test.describe("Create document as a signed-in user", () => {
  test(
    "New document creates a document owned by the signed-in user and opens it",
    {
      tag: ["@defect", "@documents", "@real-backend"],
      annotation: {
        type: "defect",
        description:
          "POST /api/v1/documents returns 401 'owner_id is required' for a signed-in user",
      },
    },
    async ({ page }) => {
      const account = await registerAccount(page.request);

      await test.step("Sign in through the login form", async () => {
        await page.goto("/login");
        await page.getByLabel("Email").fill(account.email);
        await page.getByLabel("Password", { exact: true }).fill(account.password);
        await page.getByRole("button", { name: "Sign in" }).click();
        await expect(page).toHaveURL(/\/dashboard/);
        await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
      });

      const profileId = await test.step("Read the signed-in user's id", async () => {
        const token = await page.evaluate(() => localStorage.getItem("otter_access_token"));
        expect(token, "access token stored after sign-in").toBeTruthy();
        const profile = await page.request.get("/api/v1/auth/profile", {
          headers: { Authorization: `Bearer ${token}` },
        });
        expect(profile.status(), await profile.text()).toBe(200);
        const body = await profile.json();
        return String(body.id);
      });

      await test.step("Open Documents from the sidebar", async () => {
        await page.getByRole("link", { name: "Documents" }).click();
        await expect(page.getByRole("heading", { name: "Documents" })).toBeVisible();
      });

      const created = await test.step("Press New document", async () => {
        const createResponse = page.waitForResponse(
          (r) =>
            r.request().method() === "POST" &&
            new URL(r.url()).pathname.replace(/\/$/, "") === "/api/v1/documents",
        );
        await page.getByRole("button", { name: "New document" }).click();
        const response = await createResponse;
        expect(response.status(), `create response: ${await response.text()}`).toBe(201);
        return response.json();
      });

      await test.step("The new document is owned by the signed-in user and opens", async () => {
        expect(created.owner_id).toBe(profileId);
        await expect(page).toHaveURL(new RegExp(`/documents/${created.id}$`));
        await expect(page.getByRole("button", { name: "Untitled document" })).toBeVisible();
      });
    },
  );
});
