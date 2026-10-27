import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

// Legacy data, verbatim from tests/legacy-suites/cypress/cypress/fixtures/user.json.
export const legacyUser = {
  id: "user-123",
  email: "alex.morgan@example.test",
  displayName: "Alex Morgan",
  createdAt: "2025-01-15T12:00:00.000Z",
} as const;

// Legacy data, verbatim from tests/legacy-suites/cypress/cypress/fixtures/settings.json.
export const legacySettings = {
  notificationEmail: true,
  notificationInApp: true,
  notificationDesktop: false,
  theme: "light",
  language: "en",
} as const;

// Legacy data, verbatim from the it() body of settings.cy.js.
export const legacyProfileUpdate = { displayName: "Casey Taylor" } as const;

export type ProfileUser = {
  // A real auth-service id is a UUID taken from the registration response, not the stub id.
  LegacyId: string;
  Id: string;
  // Registration needs a unique address per test; the stub address is kept for traceability.
  LegacyEmail: string;
  Email: string;
  DisplayName: string;
  NewDisplayName: string;
  // GET /api/v1/settings for a freshly registered user returns theme "system", not the stub's "light".
  LegacyTheme: string;
  Theme: string;
  accessToken: string;
};

type Fixtures = { profileUser: ProfileUser };

export const test = base.extend<Fixtures>({
  profileUser: async ({ request, page }, provide) => {
    const email = `cypress-settings-${randomUUID()}@example.com`;
    const registration = await request.post("/api/v1/auth/register", {
      data: { displayName: legacyUser.displayName, email, password: "Settings-Test-2026!" },
    });
    await expect(registration).toBeOK();
    const tokens = await registration.json();
    expect(tokens.user.email).toBe(email);
    expect(tokens.user.displayName).toBe(legacyUser.displayName);
    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);
    await provide({
      LegacyId: legacyUser.id,
      Id: tokens.user.id,
      LegacyEmail: legacyUser.email,
      Email: email,
      DisplayName: legacyUser.displayName,
      NewDisplayName: legacyProfileUpdate.displayName,
      LegacyTheme: legacySettings.theme,
      Theme: "system",
      accessToken: tokens.accessToken,
    });
  },
});
export { expect } from "@playwright/test";
