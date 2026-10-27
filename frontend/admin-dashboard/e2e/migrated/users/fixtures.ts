import { expect, type Page, type Response } from "@playwright/test";
import { adminTest, expectGatewaySession, type AdminSession } from "../support/admin-session";

export const LEGACY_SOURCE =
  "tests/legacy-suites/selenium/src/test/java/com/otterworks/legacy/admin/tests/UsersTest.java";

/** Values copied verbatim from UsersTest.java / UsersPage.java (the legacy data). */
export const UsersLegacyData = {
  path: "/users",
  heading: "User Management",
  searchText: "alex",
  // UsersPage located the search box by this placeholder; kept as data only, never as identity.
  LegacySearchPlaceholder: "Search by name or email",
  // The accessible name of the same input comes from its <mat-label> (users.component.ts template).
  searchLabel: "Search users",
  roleFilterLabel: "Role",
  // Options the Role mat-select renders (users.component.ts template); not in the legacy code.
  roleOptions: ["All Roles", "Admin", "Editor", "Viewer"],
} as const;

export class UsersPage {
  constructor(private readonly page: Page, private readonly session: AdminSession) {}

  readonly heading = () => this.page.getByRole("heading", { level: 1 });
  readonly searchBox = () => this.page.getByRole("textbox", { name: UsersLegacyData.searchLabel });
  readonly roleFilter = () => this.page.getByRole("combobox", { name: UsersLegacyData.roleFilterLabel });
  readonly roleOptions = () => this.page.getByRole("listbox", { name: UsersLegacyData.roleFilterLabel }).getByRole("option");

  /** Opens /users and proves the list came from the real gateway with this session's token. */
  async open(): Promise<Response> {
    const usersResponse = this.page.waitForResponse(response =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v1/admin/users" &&
      response.request().headers()["authorization"] === `Bearer ${this.session.accessToken}`,
    );
    await this.page.goto(UsersLegacyData.path);
    const response = await usersResponse;
    expect(response.status()).toBe(200);
    await expect(this.page).toHaveURL(/\/users$/);
    await expectGatewaySession(this.page, this.session);
    return response;
  }
}

export const test = adminTest.extend<{ usersPage: UsersPage }>({
  usersPage: async ({ page, adminSession }, use) => {
    await use(new UsersPage(page, adminSession));
  },
});

export { expect };
