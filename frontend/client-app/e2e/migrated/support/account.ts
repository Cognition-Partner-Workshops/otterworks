import { randomUUID } from "node:crypto";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export type ClientAccount = {
  id: string;
  email: string;
  displayName: string;
  password: string;
  accessToken: string;
  refreshToken: string;
  headers: { Authorization: string };
};

export type LegacyAccountFields = {
  LegacyUserId: string;
  UserId: string;
  LegacyEmail: string;
  Email: string;
  DisplayName: string;
  Password: string;
};

export async function registerUser(
  request: APIRequestContext,
  page: Page | undefined,
  {
    displayName,
    emailPrefix = "otterworks-e2e",
    email,
    password = "Documents-Test-2026!",
  }: { displayName: string; emailPrefix?: string; email?: string; password?: string },
): Promise<ClientAccount> {
  const registeredEmail = email ?? `${emailPrefix}-${randomUUID()}@example.test`;
  const registration = await request.post("/api/v1/auth/register", {
    data: { displayName, email: registeredEmail, password },
  });

  await expect(registration).toBeOK();
  const tokens = (await registration.json()) as {
    accessToken: string;
    refreshToken: string;
    user: { id: string; email: string; displayName: string };
  };
  const headers = { Authorization: `Bearer ${tokens.accessToken}` };
  expect(tokens.user).toMatchObject({ email: registeredEmail, displayName });
  if (page) {
    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);
  }
  return {
    id: tokens.user.id,
    email: tokens.user.email,
    displayName: tokens.user.displayName,
    password,
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
    headers,
  };
}

export function legacyAccountFields(
  account: ClientAccount,
  legacyUser: { id: string; email: string; displayName: string },
): LegacyAccountFields {
  return {
    LegacyUserId: legacyUser.id,
    UserId: account.id,
    LegacyEmail: legacyUser.email,
    Email: account.email,
    DisplayName: account.displayName,
    Password: account.password,
  };
}
