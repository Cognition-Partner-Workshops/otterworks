import { randomUUID } from "node:crypto";
import {
  expect,
  test as base,
  type APIRequestContext,
} from "@playwright/test";

export const API_GATEWAY_URL =
  process.env.API_GATEWAY_URL ?? "http://localhost:8080";

interface Customer {
  id: string;
  email: string;
  password: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
}

interface CustomerDocument {
  id: string;
  title: string;
}

interface CustomerFile {
  id: string;
  name: string;
}

interface SmokeFixtures {
  runId: string;
  api: APIRequestContext;
  customer: Customer;
  customerDocument: CustomerDocument;
  customerFile: CustomerFile;
}

export const test = base.extend<SmokeFixtures>({
  runId: async ({}, provide) => {
    await provide(randomUUID());
  },

  api: async ({ playwright }, provide) => {
    const context = await playwright.request.newContext({
      baseURL: API_GATEWAY_URL,
    });
    await provide(context);
    await context.dispose();
  },

  customer: async ({ api, runId }, provide) => {
    const email = `smoke-dashboard-recent-${runId}@otterworks.test`;
    const password = `Smoke-${runId}`;
    const displayName = `Smoke Customer ${runId.slice(0, 8)}`;
    const response = await api.post("/api/v1/auth/register", {
      data: { email, password, displayName },
    });
    await expect(response).toBeOK();
    expect(response.status()).toBe(201);

    const result = (await response.json()) as {
      accessToken: string;
      refreshToken: string;
      user: { id: string };
    };
    await provide({
      id: result.user.id,
      email,
      password,
      displayName,
      accessToken: result.accessToken,
      refreshToken: result.refreshToken,
    });
  },

  storageState: [
    async ({ customer, baseURL }, provide) => {
      await provide({
        cookies: [],
        origins: [
          {
            origin: new URL(baseURL!).origin,
            localStorage: [
              { name: "otter_access_token", value: customer.accessToken },
              { name: "otter_refresh_token", value: customer.refreshToken },
            ],
          },
        ],
      });
    },
    { scope: "test" },
  ],

  customerDocument: async ({ api, customer, runId }, provide) => {
    const title = `Smoke document ${runId}`;
    const response = await api.post("/api/v1/documents", {
      headers: { Authorization: `Bearer ${customer.accessToken}` },
      data: { title },
    });
    await expect(response).toBeOK();
    expect(response.status()).toBe(201);

    const result = (await response.json()) as { id: string };
    await provide({ id: result.id, title });
  },

  customerFile: async (
    { api, customer, runId, customerDocument },
    provide,
  ) => {
    // Uploaded after the document so Recent's newest-first order is deterministic.
    void customerDocument;
    const name = `smoke-file-${runId}.txt`;
    const response = await api.post("/api/v1/files/upload", {
      headers: { Authorization: `Bearer ${customer.accessToken}` },
      multipart: {
        file: {
          name,
          mimeType: "text/plain",
          buffer: Buffer.from(`smoke ${runId}`),
        },
      },
    });
    await expect(response).toBeOK();

    const result = (await response.json()) as {
      file: { id: string; name: string };
    };
    await provide({ id: result.file.id, name: result.file.name });
  },
});

export { expect };

export const signedOut = {
  storageState: { cookies: [], origins: [] },
};
