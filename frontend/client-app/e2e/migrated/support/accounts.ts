import { randomUUID } from "node:crypto";
import { expect, type APIRequestContext } from "@playwright/test";

export async function registerAccount(
  request: APIRequestContext,
  account: { displayName: string; email: string; password: string },
): Promise<{
  accessToken: string;
  refreshToken: string;
  user: { id: string; email: string; displayName: string };
}> {
  const response = await request.post("/api/v1/auth/register", { data: account });
  await expect(response).toBeOK();
  return response.json();
}

export function disposableEmail(localPart: string, domain: string): string {
  return `${localPart}-${randomUUID()}@${domain}`;
}
