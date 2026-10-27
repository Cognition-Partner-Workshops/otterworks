import type { Locator, Page } from "@playwright/test";

export class SettingsPage {
  readonly heading: Locator;
  readonly fullName: Locator;
  readonly email: Locator;
  readonly saveChanges: Locator;
  readonly emailNotifications: Locator;

  constructor(page: Page) {
    this.heading = page.getByRole("heading", { name: "Settings", exact: true });
    this.fullName = page.getByLabel("Full name", { exact: true });
    this.email = page.getByLabel("Email", { exact: true });
    this.saveChanges = page.getByRole("button", { name: "Save changes", exact: true });
    // The toggle has no accessible name or aria-checked state; scope it to its text-only row.
    this.emailNotifications = page
      .getByRole("main")
      .locator("div")
      .filter({ hasText: /^Email notificationsReceive notifications via email$/ })
      .getByRole("button");
  }
}
