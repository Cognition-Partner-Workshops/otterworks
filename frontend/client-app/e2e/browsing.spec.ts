import { execFileSync } from "node:child_process";
import { randomBytes } from "node:crypto";
import { test, expect, type APIRequestContext, type Page } from "@playwright/test";

const GATEWAY = process.env.API_GATEWAY_URL ?? "http://localhost:8080";
const PASSWORD = `Qa-${randomBytes(6).toString("hex")}!9`;

interface Session {
  id: string;
  email: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
}

async function registerViaGateway(request: APIRequestContext): Promise<Session> {
  const email = `browse-${Date.now()}-${randomBytes(3).toString("hex")}@otterworks.test`;
  const displayName = "Browse Tester";
  const response = await request.post(`${GATEWAY}/api/v1/auth/register`, {
    data: { email, password: PASSWORD, displayName },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  return {
    id: body.user.id,
    email,
    displayName,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

async function signIn(page: Page, session: Session) {
  await page.goto("/");
  await page.evaluate(
    ([access, refresh]) => {
      localStorage.setItem("otter_access_token", access);
      localStorage.setItem("otter_refresh_token", refresh);
    },
    [session.accessToken, session.refreshToken]
  );
}

function authHeaders(session: Session) {
  return { Authorization: `Bearer ${session.accessToken}` };
}

async function createFolder(request: APIRequestContext, session: Session, name: string, parentId?: string) {
  const response = await request.post(`${GATEWAY}/api/v1/folders`, {
    headers: authHeaders(session),
    data: { name, parent_id: parentId ?? null, owner_id: session.id },
  });
  expect(response.status()).toBe(201);
  return (await response.json()) as { id: string; name: string };
}

async function uploadFile(request: APIRequestContext, session: Session, name: string, folderId?: string) {
  const response = await request.post(`${GATEWAY}/api/v1/files/upload`, {
    headers: authHeaders(session),
    multipart: {
      owner_id: session.id,
      ...(folderId ? { folder_id: folderId } : {}),
      file: { name, mimeType: "text/plain", buffer: Buffer.from(`browsing e2e ${name}`) },
    },
  });
  expect([200, 201]).toContain(response.status());
  const body = await response.json();
  return (body.file ?? body) as { id: string; name: string };
}

function seedNotification(userId: string, title: string): string | null {
  const id = `qa-e2e-${randomBytes(8).toString("hex")}`;
  const item = {
    id: { S: id },
    userId: { S: userId },
    type: { S: "share" },
    title: { S: title },
    message: { S: `${title} message` },
    resourceId: { S: "" },
    resourceType: { S: "" },
    actorId: { S: "" },
    read: { BOOL: false },
    deliveredVia: { L: [{ S: "IN_APP" }] },
    createdAt: { S: new Date().toISOString() },
  };
  try {
    execFileSync(
      "docker",
      [
        "exec", "otterworks-localstack", "awslocal", "dynamodb", "put-item",
        "--table-name", "otterworks-notifications", "--item", JSON.stringify(item),
      ],
      { stdio: "pipe", timeout: 30_000 }
    );
    return id;
  } catch {
    return null;
  }
}

function toggleFor(page: Page, label: string) {
  return page.getByText(label, { exact: true }).locator("xpath=../..").getByRole("button");
}

test.describe("Browsing (signed in)", () => {
  let session: Session;

  test.beforeEach(async ({ page, request }) => {
    session = await registerViaGateway(request);
    await signIn(page, session);
  });

  test("dashboard shows empty states for a new user", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
    await expect(page.getByText("No recent files")).toBeVisible();
    await expect(page.getByText("No recent documents")).toBeVisible();
    await expect(page.getByRole("link", { name: "Upload file" })).toBeVisible();
    await expect(page.getByRole("link", { name: "New document" })).toBeVisible();
  });

  test("dashboard and recent list an uploaded file", async ({ page, request }) => {
    await uploadFile(request, session, "quarterly-report.txt");
    await page.goto("/dashboard");
    await expect(page.getByText("quarterly-report.txt").first()).toBeVisible();
    await page.goto("/recent");
    await expect(page.getByRole("heading", { name: "Recent" })).toBeVisible();
    await expect(page.getByText("quarterly-report.txt").first()).toBeVisible();
    await expect(page.getByText("Today")).toBeVisible();
  });

  test("sidebar navigates between every browsing page", async ({ page }) => {
    await page.goto("/dashboard");
    const destinations: Array<[string, string, string]> = [
      ["Recent", "/recent", "Recent"],
      ["Files", "/files", "Files"],
      ["Starred", "/starred", "Starred"],
      ["Notifications", "/notifications", "Notifications"],
      ["Settings", "/settings", "Settings"],
      ["Dashboard", "/dashboard", "Dashboard"],
    ];
    const sidebar = page.locator("aside");
    for (const [label, path, heading] of destinations) {
      await sidebar.getByRole("link", { name: label, exact: true }).click();
      await expect(page).toHaveURL((url) => url.pathname === path);
      await expect(page.getByRole("heading", { name: heading, exact: true, level: 1 })).toBeVisible();
    }
  });

  test("sidebar collapses and expands", async ({ page }) => {
    await page.goto("/dashboard");
    const sidebar = page.locator("aside");
    await expect(sidebar.getByText("Recent", { exact: true })).toBeVisible();
    await page.getByRole("button", { name: "Toggle sidebar" }).click();
    await expect(sidebar.getByText("Recent", { exact: true })).toHaveCount(0);
    await page.getByRole("button", { name: "Toggle sidebar" }).click();
    await expect(sidebar.getByText("Recent", { exact: true })).toBeVisible();
  });

  test("folder browsing with breadcrumbs", async ({ page, request }) => {
    const parent = await createFolder(request, session, "Projects");
    await createFolder(request, session, "Archive", parent.id);
    await uploadFile(request, session, "plan.txt", parent.id);

    await page.goto("/files");
    await expect(page.getByText("Projects").first()).toBeVisible();
    await page.goto(`/files?folder=${parent.id}`);

    const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumbs.getByRole("link", { name: "Files" })).toBeVisible();
    await expect(crumbs.getByText("Projects")).toBeVisible();
    await expect(page.getByText("Archive").first()).toBeVisible();
    await expect(page.getByText("plan.txt").first()).toBeVisible();

    await crumbs.getByRole("link", { name: "Files" }).click();
    await expect(page).toHaveURL((url) => url.pathname === "/files" && !url.searchParams.has("folder"));
  });

  test("[REAL] BROWSE-R8: nested folder breadcrumb includes the parent folder", async ({ page, request }) => {
    test.fail(true, "[REAL] BROWSE-R8: files.tsx builds breadcrumbs as [Files, current] and drops ancestors");
    const parent = await createFolder(request, session, "Outer Folder");
    const child = await createFolder(request, session, "Inner Folder", parent.id);
    await page.goto(`/files?folder=${child.id}`);
    const crumbs = page.getByRole("navigation", { name: "Breadcrumb" });
    await expect(crumbs.getByText("Inner Folder")).toBeVisible();
    await expect(crumbs.getByRole("link", { name: "Outer Folder" })).toBeVisible({ timeout: 5_000 });
  });

  test("breadcrumb Home returns to the dashboard", async ({ page, request }) => {
    const folder = await createFolder(request, session, "Breadcrumb Home");
    await page.goto(`/files?folder=${folder.id}`);
    await page.getByRole("navigation", { name: "Breadcrumb" }).getByRole("link", { name: "Home" }).click();
    await expect(page).toHaveURL((url) => url.pathname === "/dashboard");
  });

  test("starred page shows empty state then starred items", async ({ page, request }) => {
    await page.goto("/starred");
    await expect(page.getByText("No starred items")).toBeVisible();

    const folder = await createFolder(request, session, "Favourite Folder");
    await page.evaluate(
      ([userId, folderId]) => {
        localStorage.setItem(
          "otter_starred_items",
          JSON.stringify({
            [`${userId}:${folderId}`]: { itemId: folderId, itemType: "folder", starredAt: new Date().toISOString() },
          })
        );
      },
      [session.id, folder.id]
    );
    await page.reload();
    await expect(page.getByText("Favourite Folder").first()).toBeVisible();
  });

  test("notifications panel lists seeded notifications", async ({ page }) => {
    const id = seedNotification(session.id, "Shared roadmap with you");
    test.skip(!id, "LocalStack DynamoDB not reachable via docker");
    await page.goto("/notifications");
    await expect(page.getByText("Shared roadmap with you", { exact: true })).toBeVisible();
    await expect(page.getByText("1 unread notification")).toBeVisible();
    await expect(page.getByRole("button", { name: "Mark all as read" })).toBeVisible();
  });

  test("notifications empty state", async ({ page }) => {
    await page.goto("/notifications");
    await expect(page.getByText("No notifications")).toBeVisible();
  });

  test("[REAL] BROWSE-R2: Mark all as read clears unread notifications", async ({ page }) => {
    test.fail(true, "[REAL] BROWSE-R2: client POSTs /notifications/read-all, service only routes PUT (405)");
    const id = seedNotification(session.id, "Unread for mark-all");
    test.skip(!id, "LocalStack DynamoDB not reachable via docker");
    await page.goto("/notifications");
    await page.getByRole("button", { name: "Mark all as read" }).click();
    await expect(page.getByText("1 unread notification")).toHaveCount(0, { timeout: 5_000 });
  });

  test("[REAL] BROWSE-R4: bell badge shows the unread count", async ({ page }) => {
    test.fail(true, "[REAL] BROWSE-R4: client reads `count`, service returns `unreadCount`");
    const id = seedNotification(session.id, "Badge check");
    test.skip(!id, "LocalStack DynamoDB not reachable via docker");
    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Notifications (1 unread)" })).toBeVisible({ timeout: 5_000 });
  });

  test("settings shows profile and persists a notification preference", async ({ page, request }) => {
    await page.goto("/settings");
    await expect(page.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    await expect(page.getByLabel("Full name")).toHaveValue(session.displayName);
    await expect(page.getByRole("button", { name: "Save changes" })).toBeDisabled();

    const saved = page.waitForResponse((r) => r.url().endsWith("/api/v1/settings") && r.request().method() === "PATCH");
    await toggleFor(page, "Desktop notifications").click();
    expect((await saved).status()).toBe(200);

    const settings = await request.get(`${GATEWAY}/api/v1/settings`, { headers: authHeaders(session) });
    expect((await settings.json()).notificationDesktop).toBe(true);
  });

  test("[REAL] BROWSE-R1: settings profile save succeeds", async ({ page }) => {
    test.fail(true, "[REAL] BROWSE-R1: client PATCHes /auth/profile, auth-service only maps PUT (500)");
    await page.goto("/settings");
    await page.getByLabel("Full name").fill("Renamed Tester");
    await page.getByRole("button", { name: "Save changes" }).click();
    await expect(page.getByText("Profile updated successfully.")).toBeVisible({ timeout: 5_000 });
  });
});

test.describe("Landing page (signed out)", () => {
  test("landing page links to sign in and sign up", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByRole("heading", { name: "OtterWorks", exact: true })).toBeVisible();
    await expect(page.getByRole("link", { name: "Sign In" }).first()).toBeVisible();
  });

  test("protected browsing pages redirect to login", async ({ page }) => {
    for (const path of ["/dashboard", "/files", "/recent", "/starred", "/notifications", "/settings"]) {
      await page.goto(path);
      await expect(page.getByText("Sign in to your account")).toBeVisible({ timeout: 10_000 });
    }
  });
});
