import { expect, type Locator, type Page } from "@playwright/test";

export class LoginPage {
  readonly heading: Locator;
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly signInButton: Locator;
  readonly passwordVisibilityToggle: Locator;

  constructor(private readonly page: Page) {
    this.heading = page.getByRole("heading", { name: "OtterWorks Admin" });
    this.emailInput = page.getByRole("textbox", { name: "Email" });
    this.passwordInput = page.getByRole("textbox", { name: "Password" });
    this.signInButton = page.getByRole("button", { name: "Sign In" });
    // Accessibility gap: the toggle has no accessible name (its only content is an aria-hidden
    // mat-icon), so it is matched as a button by the icon ligature shown while the password is hidden.
    this.passwordVisibilityToggle = page.getByRole("button").filter({ hasText: "visibility_off" });
  }

  async open(path: string): Promise<void> {
    await this.page.goto(path);
    await expect(this.page).toHaveURL(new RegExp(`${path}$`));
    await expect(this.heading).toBeVisible();
  }

  // Accessibility gap: the error message <div> has no role (not role="alert"/"status"),
  // so it can only be found by its text (substring: the div also holds the "error" icon ligature).
  validationMessage(text: string): Locator {
    return this.page.getByText(text);
  }
}
