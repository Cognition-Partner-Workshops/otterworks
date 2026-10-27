import { test as base } from "@playwright/test";
import { legacyAccountFields, registerUser } from "../support/account";
import { SettingsPage } from "../support/settings-page";

type SettingsDesignRow = {
  TestCaseId: string;
  Instance: string;
  Name: string;
  Email: string;
  UpdatedName: string;
  Preference: string;
};
type RegisteredUser = Awaited<ReturnType<typeof registerUser>>;
type Profile = SettingsDesignRow & RegisteredUser & { ToscaEmail: string };
type Notifications = SettingsDesignRow & RegisteredUser & { ToscaExpected: string; Expected: string };
type SaveProfile = SettingsDesignRow & RegisteredUser & {
  ToscaEmail: string;
  LegacyId: string;
  LegacyEmail: string;
  LegacyTheme: string;
};
type Fixtures = {
  Profile: Profile;
  Notifications: Notifications;
  SaveProfile: SaveProfile;
  settingsPage: SettingsPage;
};

export const test = base.extend<Fixtures>({
  settingsPage: async ({ page }, use) => {
    await use(new SettingsPage(page));
  },
  Profile: async ({ request, page }, use) => {
    const account = await registerUser(request, page, {
      displayName: "Alex Morgan",
      emailPrefix: "settings-profile",
    });
    await page.goto("/settings");
    // Per-test unique account: the fixed CSV account can register only once and returns 409 on rerun.
    await use({
      TestCaseId: "TC-SET-001",
      Instance: "Profile",
      Name: "Alex Morgan",
      ToscaEmail: "alex.morgan@example.test",
      Email: account.email,
      UpdatedName: "",
      Preference: "",
      ...account,
    });
  },
  Notifications: async ({ request, page }, use) => {
    // The CSV Name is the row label and stays verbatim in the fixture.
    const account = await registerUser(request, page, {
      displayName: "Settings Notifications",
      emailPrefix: "settings-notifications",
    });
    await page.goto("/settings");
    await use({
      TestCaseId: "TC-SET-002",
      Instance: "Notifications",
      Name: "Email notifications",
      Email: "",
      UpdatedName: "",
      Preference: "",
      ToscaExpected: "Enabled",
      // The API starts true and returns false after the successful click.
      Expected: "Disabled",
      ...account,
    });
  },
  SaveProfile: async ({ request, page }, use) => {
    const account = await registerUser(request, page, {
      displayName: "Alex Morgan",
      emailPrefix: "settings-save-profile",
      password: "Settings-Test-2026!",
    });
    const legacyFields = legacyAccountFields(account, {
      id: "user-123",
      email: "alex.morgan@example.test",
      displayName: "Alex Morgan",
    });
    await page.goto("/settings");
    // Per-test unique account: the fixed CSV account can register only once and returns 409 on rerun.
    await use({
      TestCaseId: "TC-SET-003",
      Instance: "SaveProfile",
      Name: "Alex Morgan",
      ToscaEmail: "alex.morgan@example.test",
      UpdatedName: "Casey Taylor",
      Preference: "",
      LegacyId: "user-123",
      LegacyTheme: "light",
      ...account,
      ...legacyFields,
    });
  },
});

export { expect } from "@playwright/test";
