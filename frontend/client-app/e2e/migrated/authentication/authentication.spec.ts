import { test, expect } from "./fixtures";
import { ClientLoginPage, signInThroughLoginForm } from "../support/login-page";
import { legacyDetails } from "../support/traceability";

// Tosca TestStep values that the app never renders (see PARITY.md). TC-AUTH-002: login.tsx uses
// type=email without noValidate, so Chrome's constraint validation blocks submit before the Zod
// message; the field reports typeMismatch. TC-AUTH-003: register.tsx's Zod rule for an empty name
// reads "Name must be at least 2 characters" (also bdd/features/authentication.feature).
const ToscaExpected: Record<string, string> = {
  "TC-AUTH-002": "Please enter a valid email address",
  "TC-AUTH-003": "Name is required",
};

function source(id: string) {
  const details = legacyDetails({
    suite: "tosca",
    id,
    group: "tosca-Authentication",
    source: `tests/legacy-suites/tosca/TestCases/Authentication/${id}.xml`,
  });
  const tag = [...details.tag];
  const annotation: { type: string; description: string }[] = [details.annotation];
  if (ToscaExpected[id]) annotation.push({ type: "tosca-expected", description: ToscaExpected[id] });
  if (id === "TC-AUTH-001") {
    const cypress = legacyDetails({
      suite: "cypress",
      id: "CY-sign-in-01",
      group: "cypress-sign-in",
      source: "tests/legacy-suites/cypress/cypress/e2e/sign-in.cy.js",
      method: "opens the dashboard with a valid account",
    });
    tag.push(...cypress.tag);
    annotation.push(cypress.annotation);
  }
  return { tag, annotation };
}

test("TC-AUTH-001 Sign in with a valid account", source("TC-AUTH-001"), async ({ page, ValidSignIn }) => {
  const loginPage = new ClientLoginPage(page);
  let loginResult!: Awaited<ReturnType<typeof signInThroughLoginForm>>;
  await test.step("TC-AUTH-001-STEP-01 Input LoginEmail", async () => {
    await loginPage.emailInput.fill(ValidSignIn.Email);
  });
  await test.step("TC-AUTH-001-STEP-02 Input LoginPassword", async () => {
    await loginPage.passwordInput.fill(ValidSignIn.Password);
  });
  await test.step("TC-AUTH-001-STEP-03 Click SignInButton", async () => {
    loginResult = await signInThroughLoginForm(page);
  });
  await test.step("TC-AUTH-001-STEP-04 Verify DashboardHeading", async () => {
    await expect(page).toHaveURL("/dashboard");
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  });
  await test.step("CY-sign-in-01-STEP-05 Verify login response", async () => {
    expect(loginResult.loginResponse.status()).toBe(200);
    const body = (await loginResult.loginResponse.json()) as { user: { id: string } };
    expect(body.user.id).toBe(ValidSignIn.id);
  });
  await test.step("CY-sign-in-01-STEP-06 Verify profile response", async () => {
    expect(loginResult.profileResponse.status()).toBe(200);
    expect(await loginResult.profileResponse.json()).toMatchObject({
      id: ValidSignIn.id,
      email: ValidSignIn.email,
      displayName: ValidSignIn.displayName,
    });
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("otter_access_token")))
      .toBe(loginResult.accessToken);
  });
  await test.step("CY-sign-in-01-STEP-07 Verify dashboard URL and heading", async () => {
    await expect(page).toHaveURL(/\/dashboard$/);
    await expect(page.getByRole("heading", { name: "Dashboard", exact: true })).toBeVisible();
  });
  await test.step("CY-sign-in-01-STEP-08 Verify display name", async () => {
    // The header's signed-in name is a plain span with no accessible role or name.
    await expect(page.getByRole("banner").getByText(ValidSignIn.displayName, { exact: true })).toBeVisible();
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

test(
  "CY-sign-in-02 requires an email address",
  {
    ...legacyDetails({
      suite: "cypress",
      id: "CY-sign-in-02",
      group: "cypress-sign-in",
      source: "tests/legacy-suites/cypress/cypress/e2e/sign-in.cy.js",
      method: "requires an email address",
    }),
  },
  async ({ page, MissingEmail }) => {
    const loginPage = new ClientLoginPage(page);
    const loginRequests: string[] = [];
    page.on("request", (request) => {
      if (new URL(request.url()).pathname === "/api/v1/auth/login") loginRequests.push(request.url());
    });

    await test.step("CY-sign-in-02-STEP-01 Visit /login", async () => {
      await loginPage.open();
    });
    await test.step("CY-sign-in-02-STEP-02 Type password", async () => {
      await loginPage.passwordInput.fill(MissingEmail.password);
    });
    await test.step("CY-sign-in-02-STEP-03 Click button Sign in", async () => {
      await loginPage.signInButton.click();
    });
    await test.step("CY-sign-in-02-STEP-04 Verify email error visible", async () => {
      // The validation message is a plain paragraph, not linked to the input (no aria-describedby/role=alert).
      await expect(page.getByText(MissingEmail.emailError, { exact: true })).toBeVisible();
      await expect(page).toHaveURL(/\/login$/);
      expect(loginRequests).toEqual([]);
    });
  },
);
