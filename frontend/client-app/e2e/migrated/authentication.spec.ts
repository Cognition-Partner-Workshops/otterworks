import type { Page } from "@playwright/test";
import { test, expect } from "./fixtures/tosca";
import {
  InvalidEmail,
  PasswordMismatch,
  RequiredName,
  ValidSignIn,
} from "./fixtures/data/authentication";

const authenticationCsv =
  "tests/legacy-suites/tosca/TestCaseDesign/Authentication.csv";

function recordRequests(page: Page, method: string, path: string): string[] {
  const requests: string[] = [];
  page.on("request", (request) => {
    if (
      request.method() === method &&
      new URL(request.url()).pathname === path
    ) {
      requests.push(request.url());
    }
  });
  return requests;
}

test.describe("TC-AUTH-001 Sign in with a valid account", () => {
  test.use({ toscaData: ValidSignIn, signedIn: false });

  test(
    "TC-AUTH-001 Sign in with a valid account",
    {
      tag: ["@TC-AUTH-001", "@tosca-authentication"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Authentication/TC-AUTH-001.xml",
        },
        {
          type: "tosca-data",
          description: `${authenticationCsv}#ValidSignIn`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      await page.goto("/login");

      await test.step("TC-AUTH-001-STEP-01 Input LoginEmail", async () => {
        await page.getByLabel("Email").fill(toscaData.row.Email);
      });

      await test.step("TC-AUTH-001-STEP-02 Input LoginPassword", async () => {
        await page.getByLabel("Password").fill(toscaData.row.Password);
      });

      await test.step("TC-AUTH-001-STEP-03 Click SignInButton", async () => {
        await page.getByRole("button", { name: "Sign in" }).click();
      });

      await test.step(
        "TC-AUTH-001-STEP-04 Verify DashboardHeading",
        async () => {
          await expect(page).toHaveURL(/\/dashboard$/);
          await expect(
            page
              .getByRole("main")
              .getByRole("heading", { level: 1, name: "Dashboard" }),
          ).toBeVisible();
          await expect(
            page
              .getByRole("banner")
              .getByText(toscaData.workspace.user.displayName, {
                exact: true,
              }),
          ).toBeVisible();
        },
      );
    },
  );
});

test.describe("TC-AUTH-002 Validate an email address", () => {
  test.use({ toscaData: InvalidEmail, signedIn: false });

  test(
    "TC-AUTH-002 Validate an email address",
    {
      tag: ["@TC-AUTH-002", "@tosca-authentication"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Authentication/TC-AUTH-002.xml",
        },
        {
          type: "tosca-data",
          description: `${authenticationCsv}#InvalidEmail`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const loginRequests = recordRequests(page, "POST", "/api/v1/auth/login");
      const email = page.getByLabel("Email");
      await page.goto("/login");

      await test.step("TC-AUTH-002-STEP-01 Input LoginEmail", async () => {
        await email.fill(toscaData.row.InvalidEmail);
      });

      await test.step("TC-AUTH-002-STEP-02 Input LoginPassword", async () => {
        await page.getByLabel("Password").fill(toscaData.row.Password);
      });

      await test.step("TC-AUTH-002-STEP-03 Click SignInButton", async () => {
        await page.getByRole("button", { name: "Sign in" }).click();
      });

      await test.step("TC-AUTH-002-STEP-04 Verify LoginEmail", async () => {
        // type="email" with no noValidate: the browser rejects the address
        // before the form's own validation runs.
        await expect
          .poll(() =>
            email.evaluate(
              (input: HTMLInputElement) => input.validity.typeMismatch,
            ),
          )
          .toBe(true);
        await expect(email).not.toHaveJSProperty("validationMessage", "");
        await expect(page).toHaveURL(/\/login$/);
        expect(loginRequests).toEqual([]);
      });
    },
  );
});

test.describe("TC-AUTH-003 Validate required registration fields", () => {
  test.use({ toscaData: RequiredName, signedIn: false });

  test(
    "TC-AUTH-003 Validate required registration fields",
    {
      tag: ["@TC-AUTH-003", "@tosca-authentication"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Authentication/TC-AUTH-003.xml",
        },
        {
          type: "tosca-data",
          description: `${authenticationCsv}#RequiredName`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const registerRequests = recordRequests(
        page,
        "POST",
        "/api/v1/auth/register",
      );
      await page.goto("/register");

      await test.step("TC-AUTH-003-STEP-01 Input RegisterName", async () => {
        await page.getByLabel("Full name").fill(toscaData.row.Name);
      });

      await test.step("TC-AUTH-003-STEP-02 Input RegisterEmail", async () => {
        await page.getByLabel("Email").fill(toscaData.row.Email);
      });

      await test.step(
        "TC-AUTH-003-STEP-03 Input RegisterPassword",
        async () => {
          await page
            .getByLabel("Password", { exact: true })
            .fill(toscaData.row.Password);
        },
      );

      await test.step(
        "TC-AUTH-003-STEP-04 Click CreateAccountButton",
        async () => {
          await page.getByRole("button", { name: "Create account" }).click();
        },
      );

      await test.step("TC-AUTH-003-STEP-05 Verify RegisterName", async () => {
        await expect(
          page.getByText(RequiredName.expected.nameError, { exact: true }),
        ).toBeVisible();
        await expect(
          page.getByText("Please confirm your password", { exact: true }),
        ).toBeVisible();
        await expect(page).toHaveURL(/\/register$/);
        expect(registerRequests).toEqual([]);
      });
    },
  );
});

test.describe("TC-AUTH-004 Validate matching registration passwords", () => {
  test.use({ toscaData: PasswordMismatch, signedIn: false });

  test(
    "TC-AUTH-004 Validate matching registration passwords",
    {
      tag: ["@TC-AUTH-004", "@tosca-authentication"],
      annotation: [
        {
          type: "tosca-testcase",
          description:
            "tests/legacy-suites/tosca/TestCases/Authentication/TC-AUTH-004.xml",
        },
        {
          type: "tosca-data",
          description: `${authenticationCsv}#PasswordMismatch`,
        },
      ],
    },
    async ({ page, toscaData }) => {
      const registerRequests = recordRequests(
        page,
        "POST",
        "/api/v1/auth/register",
      );
      await page.goto("/register");

      await test.step("TC-AUTH-004-STEP-01 Input RegisterName", async () => {
        await page.getByLabel("Full name").fill(toscaData.row.Name);
      });

      await test.step("TC-AUTH-004-STEP-02 Input RegisterEmail", async () => {
        await page.getByLabel("Email").fill(toscaData.row.Email);
      });

      await test.step(
        "TC-AUTH-004-STEP-03 Input RegisterPassword",
        async () => {
          await page
            .getByLabel("Password", { exact: true })
            .fill(toscaData.row.Password);
        },
      );

      await test.step("TC-AUTH-004-STEP-04 Input ConfirmPassword", async () => {
        await page
          .getByLabel("Confirm password")
          .fill(toscaData.row.Confirmation);
      });

      await test.step(
        "TC-AUTH-004-STEP-05 Click CreateAccountButton",
        async () => {
          await page.getByRole("button", { name: "Create account" }).click();
        },
      );

      await test.step(
        "TC-AUTH-004-STEP-06 Verify ConfirmPassword",
        async () => {
          await expect(
            page.getByText("Passwords do not match", { exact: true }),
          ).toBeVisible();
          await expect(page).toHaveURL(/\/register$/);
          expect(registerRequests).toEqual([]);
        },
      );
    },
  );
});
