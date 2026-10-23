import {
  test,
  expect,
  type APIRequestContext,
  type Page,
} from "@playwright/test";
import { uniqueEmail, loginUser, clearAuth } from "./fixtures/test-helpers";

/**
 * Sharing journeys through the client-app share dialog and the "Shared with me" page.
 * Users and the file are seeded through the API; every assertion is made in the UI.
 */

const PASSWORD = "Passw0rd!23";

interface SeedUser {
  id: string;
  email: string;
  token: string;
}

async function seedUser(
  request: APIRequestContext,
  prefix: string,
): Promise<SeedUser> {
  const email = uniqueEmail().replace("test-", `${prefix}-`);
  const res = await request.post("/api/v1/auth/register", {
    data: { displayName: `${prefix} user`, email, password: PASSWORD },
  });
  expect(res.status(), await res.text()).toBe(201);
  const body = await res.json();
  return { id: body.user.id, email, token: body.accessToken };
}

async function seedFile(
  request: APIRequestContext,
  owner: SeedUser,
  name: string,
) {
  const res = await request.post("/api/v1/files/upload", {
    headers: { Authorization: `Bearer ${owner.token}` },
    multipart: {
      file: {
        name,
        mimeType: "text/plain",
        buffer: Buffer.from("shared via e2e"),
      },
    },
  });
  expect(res.status(), await res.text()).toBe(201);
  return (await res.json()).file.id as string;
}

async function signIn(page: Page, user: SeedUser) {
  await page.goto("/login");
  await clearAuth(page);
  await loginUser(page, user.email, PASSWORD);
  await expect(page).toHaveURL(/\/dashboard/, { timeout: 15_000 });
}

async function openShareDialog(page: Page, fileId: string, fileName: string) {
  await page.goto(`/files/${fileId}`);
  await expect(page.getByText(fileName).first()).toBeVisible();
  await page.getByRole("button", { name: "Share", exact: true }).click();
  await expect(page.getByPlaceholder("Add people by email")).toBeVisible();
}

async function shareWith(
  page: Page,
  email: string,
  permission: "view" | "edit",
) {
  await page.getByPlaceholder("Add people by email").fill(email);
  await page
    .locator("select")
    .filter({ has: page.locator('option[value="view"]') })
    .first()
    .selectOption(permission);
  await page.getByRole("button", { name: "Share", exact: true }).last().click();
  await expect(page.getByText(`Shared with ${email}`)).toBeVisible();
}

async function expectShared(page: Page, fileName: string, visible: boolean) {
  await page.goto("/shared");
  await expect(
    page.getByRole("heading", { name: /Shared with me/i }),
  ).toBeVisible();
  if (visible) {
    await expect(page.getByText(fileName)).toBeVisible();
  } else {
    await expect(page.getByText("Nothing shared with you yet")).toBeVisible();
    await expect(page.getByText(fileName)).toHaveCount(0);
  }
}

test.describe("Sharing", () => {
  test("owner shares a file as viewer and the recipient sees it in Shared with me", async ({
    page,
    request,
  }) => {
    const owner = await seedUser(request, "owner");
    const recipient = await seedUser(request, "viewer");
    const fileName = `viewer-share-${Date.now()}.txt`;
    const fileId = await seedFile(request, owner, fileName);

    await signIn(page, owner);
    await openShareDialog(page, fileId, fileName);
    await shareWith(page, recipient.email, "view");
    await expect(page.getByTitle("Remove access")).toHaveCount(1);

    await signIn(page, recipient);
    await expectShared(page, fileName, true);
  });

  test("owner upgrades a share to editor and then revokes it", async ({
    page,
    request,
  }) => {
    const owner = await seedUser(request, "owner");
    const recipient = await seedUser(request, "editor");
    const fileName = `editor-share-${Date.now()}.txt`;
    const fileId = await seedFile(request, owner, fileName);

    await signIn(page, owner);
    await openShareDialog(page, fileId, fileName);
    await shareWith(page, recipient.email, "view");

    await expect(page.getByTitle("Remove access")).toBeVisible();
    const rowSelect = page.locator("select").nth(1);
    await rowSelect.selectOption("edit");
    await expect(page.getByText("Permission updated")).toBeVisible();

    await page.getByTitle("Remove access").click();
    await expect(page.getByText("Access removed")).toBeVisible();
    await expect(page.getByTitle("Remove access")).toHaveCount(0);

    await signIn(page, recipient);
    await expectShared(page, fileName, false);
  });

  test("a user the file was never shared with does not see it", async ({
    page,
    request,
  }) => {
    const owner = await seedUser(request, "owner");
    const recipient = await seedUser(request, "recipient");
    const stranger = await seedUser(request, "stranger");
    const fileName = `private-share-${Date.now()}.txt`;
    const fileId = await seedFile(request, owner, fileName);

    await signIn(page, owner);
    await openShareDialog(page, fileId, fileName);
    await shareWith(page, recipient.email, "view");

    await signIn(page, stranger);
    await expectShared(page, fileName, false);
  });
});
