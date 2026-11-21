import {
  test,
  expect,
  expectSignedInDashboard,
  loginStatusViaApi,
  uniqueCustomerDetails,
} from "./fixtures/signed-in";

test.describe("Authentication", () => {
  test.describe("Registration — signed out", () => {
    test.use({ account: "signedOut" });

    test.beforeEach(async ({ page }) => {
      await page.goto("/register");
    });

    test("a new customer registers and lands on their dashboard signed in", async ({
      page,
      api,
      newCustomerDetails,
    }) => {
      await test.step("Fill and submit the registration form", async () => {
        await page.getByLabel("Full name").fill(newCustomerDetails.displayName);
        await page.getByLabel("Email").fill(newCustomerDetails.email);
        await page.getByLabel("Password", { exact: true }).fill(newCustomerDetails.password);
        await page.getByLabel("Confirm password").fill(newCustomerDetails.password);
        await page.getByRole("button", { name: "Create account" }).click();
      });
      await test.step("The dashboard shows the new customer's profile", async () => {
        await expectSignedInDashboard(page, newCustomerDetails);
      });
      await test.step("The account's credentials sign in through the API", async () => {
        expect(await loginStatusViaApi(api, newCustomerDetails)).toBe(200);
      });
    });

    test("registering an email that already has an account shows an error and stays on /register", async ({
      page,
      secondCustomer,
    }) => {
      await test.step("Submit the form with an existing customer's email", async () => {
        await page.getByLabel("Full name").fill(secondCustomer.displayName);
        await page.getByLabel("Email").fill(secondCustomer.email);
        await page.getByLabel("Password", { exact: true }).fill(secondCustomer.password);
        await page.getByLabel("Confirm password").fill(secondCustomer.password);
        await page.getByRole("button", { name: "Create account" }).click();
      });
      await test.step("The duplicate-account error is shown", async () => {
        await expect(page.getByText("Registration failed. This email may already be in use.")).toBeVisible();
        await expect(page).toHaveURL(/\/register$/);
      });
    });

    test("shows validation error for short name", async ({ page }) => {
      const details = uniqueCustomerDetails();
      await test.step("Submit a one-character name", async () => {
        await page.getByLabel("Full name").fill("A");
        await page.getByLabel("Email").fill(details.email);
        await page.getByLabel("Password", { exact: true }).fill(details.password);
        await page.getByLabel("Confirm password").fill(details.password);
        await page.getByRole("button", { name: "Create account" }).click();
      });
      await test.step("The name error is shown and the form is not submitted", async () => {
        await expect(page.getByText("Name must be at least 2 characters")).toBeVisible();
        await expect(page).toHaveURL(/\/register$/);
      });
    });

    test("shows validation errors for invalid emails", async ({ page }) => {
      const details = uniqueCustomerDetails();
      const email = page.getByLabel("Email");
      await test.step("Fill the rest of the form validly", async () => {
        await page.getByLabel("Full name").fill(details.displayName);
        await page.getByLabel("Password", { exact: true }).fill(details.password);
        await page.getByLabel("Confirm password").fill(details.password);
      });
      await test.step("An address without @ is blocked by the browser's email check", async () => {
        await email.fill("not-an-email");
        await page.getByRole("button", { name: "Create account" }).click();
        await expect
          .poll(() => email.evaluate((input) => (input as HTMLInputElement).validity.typeMismatch))
          .toBe(true);
        await expect(page).toHaveURL(/\/register$/);
      });
      await test.step("An address the browser accepts but the app rejects shows the app's error", async () => {
        await email.fill("customer@localhost");
        await page.getByRole("button", { name: "Create account" }).click();
        await expect(page.getByText("Please enter a valid email")).toBeVisible();
        await expect(page).toHaveURL(/\/register$/);
      });
    });

    test("shows validation error for short password", async ({ page }) => {
      const details = uniqueCustomerDetails();
      await test.step("Submit a five-character password", async () => {
        await page.getByLabel("Full name").fill(details.displayName);
        await page.getByLabel("Email").fill(details.email);
        await page.getByLabel("Password", { exact: true }).fill("short");
        await page.getByLabel("Confirm password").fill("short");
        await page.getByRole("button", { name: "Create account" }).click();
      });
      await test.step("The password-length error is shown", async () => {
        await expect(page.getByText("Password must be at least 8 characters")).toBeVisible();
        await expect(page).toHaveURL(/\/register$/);
      });
    });

    test("shows validation error for mismatched passwords", async ({ page }) => {
      const details = uniqueCustomerDetails();
      await test.step("Submit two different passwords", async () => {
        await page.getByLabel("Full name").fill(details.displayName);
        await page.getByLabel("Email").fill(details.email);
        await page.getByLabel("Password", { exact: true }).fill(details.password);
        await page.getByLabel("Confirm password").fill(`${details.password}-different`);
        await page.getByRole("button", { name: "Create account" }).click();
      });
      await test.step("The mismatch error is shown", async () => {
        await expect(page.getByText("Passwords do not match")).toBeVisible();
        await expect(page).toHaveURL(/\/register$/);
      });
    });
  });

  test.describe("Registration — signed in", () => {
    test("has link to sign in page", async ({ page }) => {
      await test.step("Open /register", async () => {
        await page.goto("/register");
      });
      await test.step("Follow the Sign in link to /login", async () => {
        await page.getByRole("link", { name: "Sign in" }).click();
        await expect(page).toHaveURL(/\/login$/);
        await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
      });
    });
  });

  test.describe("Login — signed out", () => {
    test.use({ account: "signedOut" });

    test.beforeEach(async ({ page }) => {
      await page.goto("/login");
    });

    test("a registered customer signs in and lands on their dashboard", async ({ page, secondCustomer }) => {
      await test.step("Sign in with the customer's credentials", async () => {
        await page.getByLabel("Email").fill(secondCustomer.email);
        await page.getByLabel("Password").fill(secondCustomer.password);
        await page.getByRole("button", { name: "Sign in" }).click();
      });
      await test.step("The dashboard shows the customer's profile", async () => {
        await expectSignedInDashboard(page, secondCustomer);
      });
    });

    test("shows validation error for empty email", async ({ page }) => {
      await test.step("Submit with only a password", async () => {
        await page.getByLabel("Password").fill("somepassword");
        await page.getByRole("button", { name: "Sign in" }).click();
      });
      await test.step("The email error is shown", async () => {
        await expect(page.getByText("Please enter a valid email")).toBeVisible();
        await expect(page).toHaveURL(/\/login$/);
      });
    });

    test("shows validation error for empty password", async ({ page }) => {
      await test.step("Submit with only an email", async () => {
        await page.getByLabel("Email").fill(uniqueCustomerDetails().email);
        await page.getByRole("button", { name: "Sign in" }).click();
      });
      await test.step("The password error is shown", async () => {
        await expect(page.getByText("Password is required")).toBeVisible();
        await expect(page).toHaveURL(/\/login$/);
      });
    });

    test("shows error for invalid credentials", async ({ page }) => {
      const unknown = uniqueCustomerDetails("Unknown");
      await test.step("Sign in with an email that has no account", async () => {
        await page.getByLabel("Email").fill(unknown.email);
        await page.getByLabel("Password").fill(unknown.password);
        await page.getByRole("button", { name: "Sign in" }).click();
      });
      await test.step("The invalid-credentials error is shown and the visitor stays on /login", async () => {
        await expect(page.getByText("Invalid email or password. Please try again.")).toBeVisible();
        await expect(page).toHaveURL(/\/login$/);
      });
    });
  });

  test.describe("Login — signed in", () => {
    test.beforeEach(async ({ page }) => {
      await page.goto("/login");
    });

    test("renders login form with email and password fields", async ({ page }) => {
      await expect(page.getByLabel("Email")).toBeVisible();
      await expect(page.getByLabel("Password")).toBeVisible();
      await expect(page.getByRole("button", { name: "Sign in" })).toBeVisible();
    });

    test("toggles password visibility", async ({ page }) => {
      const password = page.getByLabel("Password");
      await test.step("The password is masked by default", async () => {
        await password.fill("Visible-Secret-1");
        await expect(password).toHaveAttribute("type", "password");
      });
      await test.step("The show-password toggle reveals it", async () => {
        // Standard exception: the eye toggle is an icon-only button with no accessible name; reach it by Tab from the password field.
        await password.focus();
        await page.keyboard.press("Tab");
        await page.keyboard.press("Enter");
        await expect(password).toHaveAttribute("type", "text");
        await expect(password).toHaveValue("Visible-Secret-1");
      });
    });

    test("has link to registration page", async ({ page }) => {
      await page.getByRole("link", { name: "Create one" }).click();
      await expect(page).toHaveURL(/\/register$/);
      await expect(page.getByRole("button", { name: "Create account" })).toBeVisible();
    });

    test("displays OtterWorks logo and branding", async ({ page }) => {
      await expect(page.getByAltText("OtterWorks logo")).toBeVisible();
      await expect(page.getByRole("link", { name: "OtterWorks logo OtterWorks" })).toHaveAttribute("href", "/");
      await expect(page.getByText("Sign in to your account")).toBeVisible();
    });
  });
});
