import { randomUUID } from "node:crypto";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export async function registerUser(
  request: APIRequestContext,
  page: Page,
  { displayName, emailPrefix }: { displayName: string; emailPrefix: string },
) {
  const password = "Documents-Test-2026!";
  let email = `${emailPrefix}-${randomUUID()}@example.test`;
  let registration = await request.post("/api/v1/auth/register", {
    data: { displayName, email, password },
  });

  if (registration.status() === 400 || registration.status() === 422) {
    const rejection = await registration.text();
    if (/email/i.test(rejection)) {
      email = `${emailPrefix}-${randomUUID()}@example.com`;
      registration = await request.post("/api/v1/auth/register", {
        data: { displayName, email, password },
      });
    }
  }

  await expect(registration).toBeOK();
  const tokens = (await registration.json()) as {
    accessToken: string;
    refreshToken: string;
  };
  const headers = { Authorization: `Bearer ${tokens.accessToken}` };
  await page.addInitScript(({ accessToken, refreshToken }) => {
    localStorage.setItem("otter_access_token", accessToken);
    localStorage.setItem("otter_refresh_token", refreshToken);
  }, tokens);
  return { email, displayName, accessToken: tokens.accessToken, headers };
}
