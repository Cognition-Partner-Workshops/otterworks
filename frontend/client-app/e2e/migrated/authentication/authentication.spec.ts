import { test, expect } from "./fixtures";

// Tosca TestStep values that the app never renders (see PARITY.md). TC-AUTH-002: login.tsx uses
// type=email without noValidate, so Chrome's constraint validation blocks submit before the Zod
// message; the field reports typeMismatch. TC-AUTH-003: register.tsx's Zod rule for an empty name
// reads "Name must be at least 2 characters" (also bdd/features/authentication.feature).
const ToscaExpected: Record<string, string> = {
  "TC-AUTH-002": "Please enter a valid email address",
  "TC-AUTH-003": "Name is required",
};

function source(id: string) {
  const annotation = [{ type: "tosca", description: `tests/legacy-suites/tosca/TestCases/Authentication/${id}.xml` }];
  if (ToscaExpected[id]) annotation.push({ type: "tosca-expected", description: ToscaExpected[id] });
  return { tag: [`@${id}`, "@tosca-Authentication"], annotation };
}

test("TC-AUTH-001 Sign in with a valid account", source("TC-AUTH-001"), async ({ page, ValidSignIn }) => {
  await test.step("TC-AUTH-001-STEP-01 Input LoginEmail", async () => {
    await page.getByLabel("Email").fill(ValidSignIn.Email);
  });
  await test.step("TC-AUTH-001-STEP-02 Input LoginPassword", async () => {
    await page.getByLabel("Password", { exact: true }).fill(ValidSignIn.Password);
  });
  await test.step("TC-AUTH-001-STEP-03 Click SignInButton", async () => {
    await page.getByRole("button", { name: "Sign in" }).click();
  });
  await test.step("TC-AUTH-001-STEP-04 Verify DashboardHeading", async () => {
    await expect(page).toHaveURL("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  });
});

test("TC-AUTH-002 Validate an email address", source("TC-AUTH-002"), async ({ page, InvalidEmail }) => {
  const email = page.getByLabel("Email");
  await test.step("TC-AUTH-002-STEP-01 Input LoginEmail", async () => {
    await email.fill(InvalidEmail.InvalidEmail);
  });
  await test.step("TC-AUTH-002-STEP-02 Input LoginPassword", async () => {
    await page.getByLabel("Password", { exact: true }).fill(InvalidEmail.Password);
  });
  await test.step("TC-AUTH-002-STEP-03 Click SignInButton", async () => {
    await page.getByRole("button", { name: "Sign in" }).click();
  });
  await test.step("TC-AUTH-002-STEP-04 Verify LoginEmail", async () => {
    await expect.poll(() => email.evaluate((el: HTMLInputElement) => el.validity.typeMismatch)).toBe(true);
    await expect(page).toHaveURL("/login");
  });
});

test("TC-AUTH-003 Validate required registration fields", source("TC-AUTH-003"), async ({ page, RequiredName }) => {
  await test.step("TC-AUTH-003-STEP-01 Input RegisterName", async () => {
    await page.getByLabel("Full name").fill(RequiredName.Name);
  });
  await test.step("TC-AUTH-003-STEP-02 Input RegisterEmail", async () => {
    await page.getByLabel("Email").fill(RequiredName.Email);
  });
  await test.step("TC-AUTH-003-STEP-03 Input RegisterPassword", async () => {
    await page.getByLabel("Password", { exact: true }).fill(RequiredName.Password);
  });
  await test.step("TC-AUTH-003-STEP-04 Click CreateAccountButton", async () => {
    await page.getByRole("button", { name: "Create account" }).click();
  });
  await test.step("TC-AUTH-003-STEP-05 Verify RegisterName", async () => {
    // Field errors are plain <p> elements not linked via aria-describedby.
    await expect(page.getByText("Name must be at least 2 characters", { exact: true })).toBeVisible();
    await expect(page).toHaveURL("/register");
  });
});

test("TC-AUTH-004 Validate matching registration passwords", source("TC-AUTH-004"), async ({ page, PasswordMismatch }) => {
  await test.step("TC-AUTH-004-STEP-01 Input RegisterName", async () => {
    await page.getByLabel("Full name").fill(PasswordMismatch.Name);
  });
  await test.step("TC-AUTH-004-STEP-02 Input RegisterEmail", async () => {
    await page.getByLabel("Email").fill(PasswordMismatch.Email);
  });
  await test.step("TC-AUTH-004-STEP-03 Input RegisterPassword", async () => {
    await page.getByLabel("Password", { exact: true }).fill(PasswordMismatch.Password);
  });
  await test.step("TC-AUTH-004-STEP-04 Input ConfirmPassword", async () => {
    await page.getByLabel("Confirm password").fill(PasswordMismatch.Confirmation);
  });
  await test.step("TC-AUTH-004-STEP-05 Click CreateAccountButton", async () => {
    await page.getByRole("button", { name: "Create account" }).click();
  });
  await test.step("TC-AUTH-004-STEP-06 Verify ConfirmPassword", async () => {
    // Field errors are plain <p> elements not linked via aria-describedby.
    await expect(page.getByText("Passwords do not match", { exact: true })).toBeVisible();
    await expect(page).toHaveURL("/register");
  });
});
