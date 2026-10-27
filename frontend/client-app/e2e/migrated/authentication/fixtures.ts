import { test as base } from "@playwright/test";
import { registerUser, type ClientAccount } from "../support/account";
import { legacySignIn } from "../support/legacy-sign-in";

type DesignRow = {
  TestCaseId: string;
  Instance: string;
  Email: string;
  Password: string;
  Name: string;
  InvalidEmail: string;
  Confirmation: string;
};

type Fixtures = {
  ValidSignIn: DesignRow & ClientAccount & {
    ToscaEmail: string;
    LegacyEmail: string;
    LegacyId: string;
  };
  InvalidEmail: DesignRow;
  RequiredName: DesignRow;
  PasswordMismatch: DesignRow;
  MissingEmail: { password: string; emailError: string; LegacyEmail: string; LegacyId: string };
};

export const test = base.extend<Fixtures>({
  ValidSignIn: async ({ request, page }, use) => {
    // The CSV account is a shared persistent user; register a disposable one with the CSV password instead.
    const account = await registerUser(request, undefined, {
      displayName: legacySignIn.displayName,
      emailPrefix: "alex.morgan",
      password: "DemoPass123!",
    });
    const ValidSignIn: Fixtures["ValidSignIn"] = {
      TestCaseId: "TC-AUTH-001",
      Instance: "ValidSignIn",
      ...account,
      Email: account.email,
      Password: account.password,
      Name: "",
      InvalidEmail: "",
      Confirmation: "",
      ToscaEmail: "alex.morgan@example.test",
      LegacyEmail: legacySignIn.email,
      LegacyId: legacySignIn.user.id,
    };
    await page.goto("/login");
    await use(ValidSignIn);
  },
  InvalidEmail: async ({ page }, use) => {
    await page.goto("/login");
    await use({
      TestCaseId: "TC-AUTH-002",
      Instance: "InvalidEmail",
      Email: "alex.morgan@example.test",
      Password: "DemoPass123!",
      Name: "",
      InvalidEmail: "not-an-address",
      Confirmation: "",
    });
  },
  RequiredName: async ({ page }, use) => {
    await page.goto("/register");
    await use({
      TestCaseId: "TC-AUTH-003",
      Instance: "RequiredName",
      Email: "alex.new@example.test",
      Password: "DemoPass123!",
      Name: "",
      InvalidEmail: "",
      Confirmation: "",
    });
  },
  PasswordMismatch: async ({ page }, use) => {
    await page.goto("/register");
    await use({
      TestCaseId: "TC-AUTH-004",
      Instance: "PasswordMismatch",
      Email: "jordan.lee@example.test",
      Password: "DemoPass123!",
      Name: "Jordan Lee",
      InvalidEmail: "",
      Confirmation: "DifferentPass123!",
    });
  },
  MissingEmail: async ({}, use) => {
    await use({
      password: legacySignIn.password,
      emailError: legacySignIn.emailError,
      LegacyEmail: legacySignIn.email,
      LegacyId: legacySignIn.user.id,
    });
  },
});

export { expect } from "@playwright/test";
