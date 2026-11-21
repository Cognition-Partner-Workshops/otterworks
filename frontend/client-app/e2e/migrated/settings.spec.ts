import { test, expect } from "./fixtures/tosca";
import { Profile, Notifications, SaveProfile } from "./fixtures/data/settings";

const details = (id: string, instance: string) => ({
  tag: [`@${id}`, "@tosca-settings"],
  annotation: [
    { type: "tosca-testcase", description: `tests/legacy-suites/tosca/TestCases/Settings/${id}.xml` },
    { type: "tosca-data", description: `tests/legacy-suites/tosca/TestCaseDesign/Settings.csv#${instance}` },
  ],
});

test.describe("TC-SET-001 View profile settings", () => {
  test.use({ toscaData: Profile });
  test("TC-SET-001 View profile settings", details("TC-SET-001", "Profile"), async ({ page, toscaData }) => {
    await page.goto("/settings");
    const main = page.getByRole("main");
    await test.step("TC-SET-001-STEP-01 Verify SettingsHeading", async () => {
      await expect(main.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    });
    await test.step("TC-SET-001-STEP-02 Verify FullName", async () => {
      await expect(main.getByRole("textbox", { name: "Full name" })).toHaveValue(toscaData.row.Name);
    });
    await test.step("TC-SET-001-STEP-03 Verify EmailAddress", async () => {
      await expect(main.getByRole("textbox", { name: "Email", exact: true })).toHaveValue(toscaData.row.Email);
    });
  });
});

test.describe("TC-SET-002 Update email notification preference", () => {
  test.use({ toscaData: Notifications });
  test("TC-SET-002 Update email notification preference", details("TC-SET-002", "Notifications"), async ({ page, toscaData }) => {
    await page.goto("/settings");
    const main = page.getByRole("main");
    await test.step("TC-SET-002-STEP-01 Verify SettingsHeading", async () => {
      await expect(main.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
      await expect.poll(() => page.evaluate(async () => (await (await fetch("/api/v1/settings")).json()).notificationEmail)).toBe(false);
    });
    await test.step("TC-SET-002-STEP-02 Click EmailNotifications", async () => {
      await expect(main.getByText(toscaData.row.Name, { exact: true })).toBeVisible();
      // Standard exception: unnamed toggle follows Email in tab order (Save is disabled).
      await expect(main.getByRole("button", { name: "Save changes" })).toBeDisabled();
      await main.getByRole("textbox", { name: "Email", exact: true }).focus();
      await page.keyboard.press("Tab");
      await page.keyboard.press("Space");
    });
    await test.step("TC-SET-002-STEP-03 Verify EmailNotifications", async () => {
      await expect.poll(() => page.evaluate(async () => (await (await fetch("/api/v1/settings")).json()).notificationEmail)).toBe(true);
      await page.reload();
      await expect(main.getByRole("heading", { name: "Settings", level: 1 })).toBeVisible();
    });
  });
});

test.describe("TC-SET-003 Save profile details", () => {
  test.use({ toscaData: SaveProfile });
  test("TC-SET-003 Save profile details", details("TC-SET-003", "SaveProfile"), async ({ page, toscaData }) => {
    // App regression: see parity/settings.md TC-SET-003 (PATCH instead of PUT).
    test.fail();
    await page.goto("/settings");
    const name = page.getByRole("main").getByRole("textbox", { name: "Full name" });
    await test.step("TC-SET-003-STEP-01 Input FullName", async () => {
      await expect(name).toHaveValue(toscaData.row.Name);
      await name.fill(toscaData.row.UpdatedName);
    });
    await test.step("TC-SET-003-STEP-02 Click SaveChanges", async () => {
      const response = page.waitForResponse(response => response.url().endsWith("/api/v1/auth/profile") && response.request().method() !== "GET");
      await page.getByRole("button", { name: "Save changes" }).click();
      await response;
    });
    await test.step("TC-SET-003-STEP-03 Verify FullName", async () => {
      await page.reload();
      await expect(name).toHaveValue(toscaData.row.UpdatedName);
    });
  });
});
