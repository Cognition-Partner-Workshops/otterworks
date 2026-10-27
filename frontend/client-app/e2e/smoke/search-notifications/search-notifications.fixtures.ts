// Playwright fixture callbacks take a `use` argument, which the React hooks rule misreads as a hook.
/* eslint-disable react-hooks/rules-of-hooks */
import { randomUUID } from "node:crypto";
import {
  test as base,
  expect,
  type APIRequestContext,
} from "@playwright/test";

const GATEWAY_URL = process.env.API_GATEWAY_URL || "http://localhost:8080";
const SEARCH_INDEX_TIMEOUT = 30_000;
const NOTIFICATION_DELIVERY_TIMEOUT = 30_000;

export interface Customer {
  id: string;
  email: string;
  password: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
}

export interface SearchableDocument {
  id: string;
  title: string;
  searchTerm: string;
}

export interface SharedFileNotification {
  notificationId: string;
  fileId: string;
  fileName: string;
  sharer: Customer;
}

type Fixtures = {
  customer: Customer;
  searchableDocument: SearchableDocument;
  sharedFileNotification: SharedFileNotification;
};

type WorkerFixtures = {
  gateway: APIRequestContext;
};

/** Pass to `test.use({ storageState: signedOut })` for tests that must run without a session. */
export const signedOut = { cookies: [], origins: [] };

function bearer(customer: Customer) {
  return { Authorization: `Bearer ${customer.accessToken}` };
}

async function registerCustomer(
  gateway: APIRequestContext,
  role: string
): Promise<Customer> {
  const suffix = randomUUID();
  const email = `smoke-${role}-${suffix}@otterworks.test`;
  const password = `Sm0ke!${suffix.slice(0, 8)}`;
  const displayName = `Smoke ${role} ${suffix.slice(0, 8)}`;

  const response = await gateway.post("/api/v1/auth/register", {
    data: { displayName, email, password },
  });
  expect(response.status(), `register ${role}`).toBe(201);
  const body = await response.json();

  return {
    id: body.user.id,
    email,
    password,
    displayName,
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };
}

export const test = base.extend<Fixtures, WorkerFixtures>({
  gateway: [
    async ({ playwright }, use) => {
      const gateway = await playwright.request.newContext({ baseURL: GATEWAY_URL });
      await use(gateway);
      await gateway.dispose();
    },
    { scope: "worker" },
  ],

  customer: async ({ gateway }, use) => {
    await use(await registerCustomer(gateway, "customer"));
  },

  storageState: async ({ customer, baseURL }, use) => {
    await use({
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

  searchableDocument: async ({ gateway, customer }, use) => {
    const searchTerm = `otterquarry${randomUUID().replace(/-/g, "").slice(0, 12)}`;
    const title = `Smoke search ${searchTerm}`;

    const created = await gateway.post("/api/v1/documents", {
      headers: bearer(customer),
      data: {
        title,
        content: `Quarterly planning notes mentioning ${searchTerm}.`,
        content_type: "text/plain",
      },
    });
    expect(created.status(), "create document").toBe(201);
    const { id } = await created.json();

    // The document reaches the search index asynchronously (SNS -> SQS -> search-service).
    await expect
      .poll(
        async () => {
          const res = await gateway.get("/api/v1/search", {
            headers: bearer(customer),
            params: { q: searchTerm },
          });
          if (!res.ok()) return [];
          const body = await res.json();
          return (body.results ?? []).map((r: { id: string }) => String(r.id));
        },
        { message: "document is searchable", timeout: SEARCH_INDEX_TIMEOUT }
      )
      .toContain(String(id));

    await use({ id: String(id), title, searchTerm });
  },

  sharedFileNotification: async ({ gateway, customer }, use) => {
    const sharer = await registerCustomer(gateway, "sharer");
    const fileName = `smoke-shared-${randomUUID()}.txt`;

    const uploaded = await gateway.post("/api/v1/files/upload", {
      headers: bearer(sharer),
      multipart: {
        file: {
          name: fileName,
          mimeType: "text/plain",
          buffer: Buffer.from(`Shared with ${customer.email}`),
        },
      },
    });
    expect(uploaded.status(), "upload file").toBe(201);
    const fileId = String((await uploaded.json()).file.id);

    const shared = await gateway.post(`/api/v1/files/${fileId}/share`, {
      headers: bearer(sharer),
      data: { shared_with: customer.id, permission: "viewer", shared_by: sharer.id },
    });
    expect(shared.status(), "share file").toBe(201);

    // The notification is created asynchronously (SNS -> SQS -> notification-service).
    let notificationId = "";
    await expect
      .poll(
        async () => {
          const res = await gateway.get("/api/v1/notifications", {
            headers: bearer(customer),
          });
          if (!res.ok()) return "";
          const body = await res.json();
          const match = (body.data ?? []).find(
            (n: { resourceId?: string }) => n.resourceId === fileId
          );
          notificationId = match?.id ?? "";
          return notificationId;
        },
        { message: "file_shared notification delivered", timeout: NOTIFICATION_DELIVERY_TIMEOUT }
      )
      .not.toBe("");

    await use({ notificationId, fileId, fileName, sharer });
  },
});

export { expect };
