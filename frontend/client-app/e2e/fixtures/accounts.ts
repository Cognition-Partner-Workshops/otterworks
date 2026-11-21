import { randomUUID } from "node:crypto";
import { join } from "node:path";
import { expect, type APIRequestContext } from "@playwright/test";

export const PASSWORD = "Passw0rd!23";

export type Identity = {
  displayName: string;
  email: string;
  password: string;
};

export type Account = Identity & {
  id: string;
  accessToken: string;
  refreshToken: string;
  headers: { Authorization: string };
};

export function uniqueIdentity(label: string): Identity {
  const uuid = randomUUID();
  return {
    displayName: `Smoke ${label} ${uuid.slice(0, 8)}`,
    email: `smoke-${label}-${uuid}@otterworks.test`,
    password: PASSWORD,
  };
}

export async function registerAccount(
  request: APIRequestContext,
  label: string,
): Promise<Account> {
  const identity = uniqueIdentity(label);
  const response = await request.post("/api/v1/auth/register", {
    data: identity,
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  const accessToken: string = body.accessToken;
  return {
    ...identity,
    id: body.user.id,
    accessToken,
    refreshToken: body.refreshToken,
    headers: { Authorization: `Bearer ${accessToken}` },
  };
}

export function storageStateFor(account: Account, baseURL: string) {
  return {
    cookies: [],
    origins: [
      {
        origin: new URL(baseURL).origin,
        localStorage: [
          { name: "otter_access_token", value: account.accessToken },
          { name: "otter_refresh_token", value: account.refreshToken },
        ],
      },
    ],
  };
}

export const signedOut = { cookies: [], origins: [] };

export const SHARED_CUSTOMER_STATE = join(
  __dirname,
  "../../playwright/.auth/customer.json",
);
export const SHARED_CUSTOMER_META = join(
  __dirname,
  "../../playwright/.auth/customer.meta.json",
);
