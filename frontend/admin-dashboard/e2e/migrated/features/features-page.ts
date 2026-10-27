import { expect, type Locator, type Page } from "@playwright/test";

export class FeaturesPage {
  readonly heading: Locator;
  readonly searchBox: Locator;
  readonly switches: Locator;

  constructor(readonly page: Page) {
    this.heading = page.getByRole("heading", { level: 1, name: "Feature Flags" });
    this.searchBox = page.getByRole("textbox", { name: "Search features" });
    // Accessibility gap: each card's mat-slide-toggle renders role=switch with no accessible name and the card has
    // no role, so a flag's switch is reached by filtering the list to that flag and then taking the only switch.
    this.switches = page.getByRole("switch");
  }

  async goto(): Promise<void> {
    const featuresResponse = this.page.waitForResponse(response =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v1/admin/features",
    );
    await this.page.goto("/features");
    expect((await featuresResponse).status()).toBe(200);
    await expect(this.page).toHaveURL(/\/features$/);
  }

  flagHeading(name: string): Locator {
    return this.page.getByRole("heading", { level: 3, name, exact: true });
  }

  async search(term: string): Promise<void> {
    await this.searchBox.fill(term);
  }
}
