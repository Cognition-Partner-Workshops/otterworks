import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

// Legacy data, verbatim from tests/legacy-suites/cypress/cypress/e2e/sign-in.cy.js
// and cypress/fixtures/{auth-tokens,user}.json.
export const legacySignIn = {
  email: "alex.morgan@example.test",
  password: "DemoPass123!",
  displayName: "Alex Morgan",
  emailError: "Please enter a valid email",
  authTokens: { accessToken: "mock", refreshToken: "mock", expiresAt: 1740000000 },
  user: { id: "user-123", email: "alex.morgan@example.test", displayName: "Alex Morgan", createdAt: "2025-01-15T12:00:00.000Z" },
} as const;

export type ValidAccount = {
  LegacyEmail: string;
  email: string;
  password: string;
  displayName: string;
  LegacyId: string;
  id: string;
};

type Fixtures = { validAccount: ValidAccount; missingEmail: { password: string; emailError: string } };

export const test = base.extend<Fixtures>({
  validAccount: async ({ request }, provide) => {
    // Legacy email is a single shared address that the stubbed login accepted without an account;
    // the real auth-service rejects a second registration ("Email already registered"), so each
    // test registers a unique address on the same example.test domain.
    const email = `alex.morgan-${randomUUID()}@example.test`;
    const response = await request.post("/api/v1/auth/register", {
      data: { displayName: legacySignIn.displayName, email, password: legacySignIn.password },
    });
    await expect(response).toBeOK();
    const body = await response.json();
    expect(body.user).toMatchObject({ email, displayName: legacySignIn.displayName });
    await provide({
      LegacyEmail: legacySignIn.email,
      email,
      password: legacySignIn.password,
      displayName: legacySignIn.displayName,
      // Legacy id "user-123" came from the user.json stub; the real id is the auth-service UUID.
      LegacyId: legacySignIn.user.id,
      id: body.user.id,
    });
  },
  missingEmail: async ({}, provide) => {
    await provide({ password: legacySignIn.password, emailError: legacySignIn.emailError });
  },
});

export { expect };
