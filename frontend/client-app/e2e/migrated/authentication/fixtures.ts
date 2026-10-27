import { test as base } from "@playwright/test";
import { disposableEmail, registerAccount } from "../support/accounts";

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
  ValidSignIn: DesignRow & { ToscaEmail: string };
  InvalidEmail: DesignRow;
  RequiredName: DesignRow;
  PasswordMismatch: DesignRow;
};

export const test = base.extend<Fixtures>({
  ValidSignIn: async ({ request, page }, use) => {
    // The CSV account is a shared persistent user; register a disposable one with the CSV password instead.
    const ValidSignIn: Fixtures["ValidSignIn"] = {
      TestCaseId: "TC-AUTH-001",
      Instance: "ValidSignIn",
      Email: disposableEmail("alex.morgan", "example.test"),
      Password: "DemoPass123!",
      Name: "",
      InvalidEmail: "",
      Confirmation: "",
      ToscaEmail: "alex.morgan@example.test",
    };
    await registerAccount(request, {
      displayName: "Alex Morgan",
      email: ValidSignIn.Email,
      password: ValidSignIn.Password,
    });
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
});

export { expect } from "@playwright/test";
