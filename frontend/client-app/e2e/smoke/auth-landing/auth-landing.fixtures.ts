import { randomUUID } from "node:crypto";
import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";

/** The real API gateway (same default as the Vite dev proxy in vite.config.ts). */
export const API_GATEWAY_URL = process.env.API_GATEWAY_URL || "http://localhost:8080";

export const ACCESS_TOKEN_KEY = "otter_access_token";
export const REFRESH_TOKEN_KEY = "otter_refresh_token";

export interface CustomerDetails {
  displayName: string;
  email: string;
  password: string;
}

export interface Customer extends CustomerDetails {
  id: string;
  accessToken: string;
  refreshToken: string;
}

/** Unique, not-yet-registered customer details for this run. */
export function uniqueCustomerDetails(label = "Customer"): CustomerDetails {
  const suffix = randomUUID();
  return {
    displayName: `Smoke ${label} ${suffix.slice(0, 8)}`,
    email: `smoke-auth-landing-${suffix}@otterworks.test`,
    password: `Passw0rd!${suffix.slice(0, 6)}`,
  };
}

/** POST /api/v1/auth/register on the API gateway (auth-service AuthResponse). */
export async function registerCustomerViaApi(
  request: APIRequestContext,
  details: CustomerDetails = uniqueCustomerDetails(),
): Promise<Customer> {
  const response = await request.post(`${API_GATEWAY_URL}/api/v1/auth/register`, {
    data: details,
  });
  expect(response.status(), `register ${details.email}`).toBe(201);
  const body = await response.json();
  return {
    ...details,
    id: body.user.id,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

/** POST /api/v1/auth/login on the API gateway; returns the HTTP status. */
export async function loginStatusViaApi(
  request: APIRequestContext,
  credentials: Pick<CustomerDetails, "email" | "password">,
): Promise<number> {
  const response = await request.post(`${API_GATEWAY_URL}/api/v1/auth/login`, {
    data: credentials,
  });
  return response.status();
}

/**
 * The browser is on the dashboard and the app's session belongs to `who`: the sidebar
 * profile (filled from GET /api/v1/auth/profile with the stored token) shows their name and email.
 */
export async function expectSignedInDashboard(page: Page, who: CustomerDetails) {
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  const profile = page.getByRole("complementary");
  await expect(profile.getByText(who.email, { exact: true })).toBeVisible();
  await expect(profile.getByText(who.displayName, { exact: true })).toBeVisible();
}

type Options = {
  /** true (default): the browser opens every page signed in as `customer`. */
  signedIn: boolean;
};

type Fixtures = {
  /** Registers another fresh customer through the real auth API each time it is called. */
  registerCustomer: (label?: string) => Promise<Customer>;
  /** The customer the browser is signed in as (only when `signedIn` is true). */
  customer: Customer;
  /** A second registered customer whose session is NOT in the browser. */
  otherCustomer: Customer;
  /** Unique details for a customer that does not exist yet (to register through the UI). */
  newCustomerDetails: CustomerDetails;
  sessionCustomer: Customer | null;
};

export const test = base.extend<Options & Fixtures>({
  signedIn: [true, { option: true }],

  registerCustomer: async ({ request }, provide) => {
    await provide((label) => registerCustomerViaApi(request, uniqueCustomerDetails(label)));
  },

  sessionCustomer: async ({ signedIn, registerCustomer }, provide) => {
    await provide(signedIn ? await registerCustomer("Signed-in") : null);
  },

  // The real access/refresh tokens go into localStorage under the keys the app reads
  // (src/providers/auth-provider.tsx); applied once when the browser context is created.
  storageState: async ({ sessionCustomer, baseURL }, provide) => {
    if (!sessionCustomer) {
      await provide(undefined);
      return;
    }
    await provide({
      cookies: [],
      origins: [
        {
          origin: new URL(baseURL ?? "http://localhost:3000").origin,
          localStorage: [
            { name: ACCESS_TOKEN_KEY, value: sessionCustomer.accessToken },
            { name: REFRESH_TOKEN_KEY, value: sessionCustomer.refreshToken },
          ],
        },
      ],
    });
  },

  customer: async ({ sessionCustomer }, provide) => {
    if (!sessionCustomer) {
      throw new Error("The `customer` fixture needs `signedIn: true`; use `otherCustomer` when signed out.");
    }
    await provide(sessionCustomer);
  },

  otherCustomer: async ({ registerCustomer }, provide) => {
    await provide(await registerCustomer("Other"));
  },

  newCustomerDetails: async ({}, provide) => {
    await provide(uniqueCustomerDetails("New"));
  },
});

export { expect };
