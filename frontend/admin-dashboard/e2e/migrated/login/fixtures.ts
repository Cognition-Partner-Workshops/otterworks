import { adminTest } from "../support/admin-session";
import { LoginPage } from "./login-page";

/**
 * Legacy data from tests/legacy-suites/selenium/.../tests/LoginTest.java and pages/LoginPage.java,
 * kept verbatim. The Selenium suite has no data files; these values were inline in the Java code.
 */
export interface LegacyLoginData {
  /** LoginPage.open() -> BasePage.open("/login") */
  path: string;
  /** emptyCredentialsShowValidationMessage: errorText().contains(...) */
  emptyCredentialsMessage: string;
  /** passwordVisibilityCanBeChanged: enterPassword(...) */
  password: string;
  /** passwordVisibilityCanBeChanged: assertEquals(passwordInputType(), ...) */
  revealedPasswordType: string;
}

export const legacyLoginData: LegacyLoginData = {
  path: "/login",
  emptyCredentialsMessage: "Please enter both email and password.",
  password: "DemoPass123!",
  revealedPasswordType: "text",
};

// The login screen needs no signed-in session: do not request adminSession here, because its
// init script stores a gateway token and LoginComponent then redirects away from /login.
export const test = adminTest.extend<{ loginPage: LoginPage; legacyLogin: LegacyLoginData }>({
  loginPage: async ({ page }, use) => {
    await use(new LoginPage(page));
  },
  legacyLogin: async ({}, use) => {
    await use(legacyLoginData);
  },
});

export { expect } from "@playwright/test";
