import { expect, type Page, type Response } from "@playwright/test";

export class ClientLoginPage {
  readonly emailInput;
  readonly passwordInput;
  readonly signInButton;

  constructor(private readonly page: Page) {
    this.emailInput = page.getByLabel("Email");
    this.passwordInput = page.getByLabel("Password", { exact: true });
    this.signInButton = page.getByRole("button", { name: "Sign in", exact: true });
  }

  async open(): Promise<void> {
    await this.page.goto("/login");
    await expect(this.emailInput).toBeVisible();
  }
}

export async function signInThroughLoginForm(
  page: Page,
): Promise<{ loginResponse: Response; profileResponse: Response; accessToken: string }> {
  const loginResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "POST" &&
      new URL(response.url()).pathname === "/api/v1/auth/login",
  );
  const profileResponsePromise = page.waitForResponse(
    (response) =>
      response.request().method() === "GET" &&
      new URL(response.url()).pathname === "/api/v1/auth/profile",
  );
  await new ClientLoginPage(page).signInButton.click();
  const loginResponse = await loginResponsePromise;
  const profileResponse = await profileResponsePromise;
  expect(loginResponse.status()).toBe(200);
  const body = (await loginResponse.json()) as { accessToken: string };
  return { loginResponse, profileResponse, accessToken: body.accessToken };
}
