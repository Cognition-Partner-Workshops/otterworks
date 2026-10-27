import { expect, type Page, type Response } from "@playwright/test";
import { adminTest, openAdminPage, type AdminSession } from "../support/admin-session";
import { matSelect } from "../support/material";

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
  private readonly roles: ReturnType<typeof matSelect>;

  constructor(private readonly page: Page, private readonly session: AdminSession) {
    this.roles = matSelect(page, UsersLegacyData.roleFilterLabel);
  }

  readonly heading = () => this.page.getByRole("heading", { level: 1 });
  readonly searchBox = () => this.page.getByRole("textbox", { name: UsersLegacyData.searchLabel });
  readonly roleFilter = () => this.roles.trigger;
  readonly roleOptions = () => this.roles.options;

  /** Opens /users after proving the list request used this session's gateway token. */
  async open(): Promise<Response> {
    return openAdminPage(this.page, this.session, {
      path: UsersLegacyData.path,
      apiPath: "/api/v1/admin/users",
    });
  }
}

export const test = adminTest.extend<{ usersPage: UsersPage }>({
  usersPage: async ({ page, adminSession }, use) => {
    await use(new UsersPage(page, adminSession));
  },
});

export { expect };
