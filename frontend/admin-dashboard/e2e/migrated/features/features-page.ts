import type { Locator, Page } from "@playwright/test";
import { openAdminPage, type AdminSession } from "../support/admin-session";

export class FeaturesPage {
  readonly heading: Locator;
  readonly searchBox: Locator;
  readonly switches: Locator;

  constructor(readonly page: Page, private readonly session: AdminSession) {
    this.heading = page.getByRole("heading", { level: 1, name: "Feature Flags" });
    this.searchBox = page.getByRole("textbox", { name: "Search features" });
    // Accessibility gap: each card's mat-slide-toggle renders role=switch with no accessible name and the card has
    // no role, so a flag's switch is reached by filtering the list to that flag and then taking the only switch.
    this.switches = page.getByRole("switch");
  }

  async open(): Promise<void> {
    await openAdminPage(this.page, this.session, {
      path: "/features",
      apiPath: "/api/v1/admin/features",
    });
  }

  flagHeading(name: string): Locator {
    return this.page.getByRole("heading", { level: 3, name, exact: true });
  }

  async search(term: string): Promise<void> {
    await this.searchBox.fill(term);
  }
}
