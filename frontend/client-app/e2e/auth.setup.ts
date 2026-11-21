import { mkdirSync, writeFileSync } from "node:fs";
import { test } from "@playwright/test";
import path from "node:path";
import {
  ACCESS_TOKEN_KEY,
  API_GATEWAY_URL,
  AUTH_META_FILE,
  AUTH_STATE_FILE,
  REFRESH_TOKEN_KEY,
  registerCustomerViaApi,
  uniqueCustomerDetails,
} from "./fixtures/signed-in";

test("register shared customer and verify billing catalogue", async ({ playwright, baseURL }) => {
  const billingApi = await playwright.request.newContext({
    baseURL: baseURL ?? "http://localhost:3000",
  });
  try {
    const billingResponse = await billingApi.get("/billing-api/api/plans");
    if (!billingResponse.ok()) {
      throw new Error(
        `Billing setup check failed: GET /billing-api/api/plans returned ${billingResponse.status()}. ` +
          "Start the billing service and verify the billing database before running Playwright.",
      );
    }
    const plans = await billingResponse.json();
    if (!Array.isArray(plans) || plans.length === 0) {
      throw new Error(
        "Billing setup check failed: /billing-api/api/plans is empty. " +
          "Seed an empty local billing database additively before running Playwright; the suite never seeds or resets billing.",
      );
    }
  } finally {
    await billingApi.dispose();
  }

  const api = await playwright.request.newContext({ baseURL: API_GATEWAY_URL });
  try {
    const customer = await registerCustomerViaApi(api, uniqueCustomerDetails("Shared"));
    const origin = new URL(baseURL ?? "http://localhost:3000").origin;
    const state = {
      cookies: [],
      origins: [
        {
          origin,
          localStorage: [
            { name: ACCESS_TOKEN_KEY, value: customer.accessToken },
            { name: REFRESH_TOKEN_KEY, value: customer.refreshToken },
          ],
        },
      ],
    };

    mkdirSync(path.dirname(AUTH_STATE_FILE), { recursive: true, mode: 0o700 });
    writeFileSync(AUTH_STATE_FILE, JSON.stringify(state, null, 2), { mode: 0o600 });
    writeFileSync(
      AUTH_META_FILE,
      JSON.stringify(
        {
          id: customer.id,
          email: customer.email,
          displayName: customer.displayName,
          password: customer.password,
        },
        null,
        2,
      ),
      { mode: 0o600 },
    );
  } finally {
    await api.dispose();
  }
});
