/* eslint-disable react-hooks/rules-of-hooks */
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";
import {
  expect,
  test as base,
  type BrowserContext,
  type APIRequestContext,
  type Page,
} from "@playwright/test";

export const API_GATEWAY_URL = process.env.API_GATEWAY_URL || "http://localhost:8080";
export const ACCESS_TOKEN_KEY = "otter_access_token";
export const REFRESH_TOKEN_KEY = "otter_refresh_token";
export const AUTH_STATE_FILE = path.resolve(__dirname, "../../playwright/.auth/customer.json");
export const AUTH_META_FILE = path.resolve(__dirname, "../../playwright/.auth/customer.meta.json");
const BILLING_DB_CONTAINER =
  process.env.BILLING_DB_CONTAINER || "otterworks-billing-service-db-1";
const SEARCH_INDEX_TIMEOUT = 30_000;
const NOTIFICATION_DELIVERY_TIMEOUT = 30_000;

export type Account = "shared" | "fresh" | "signedOut";
type StorageState = Awaited<ReturnType<BrowserContext["storageState"]>>;

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

export interface CustomerDocument {
  id: string;
  title: string;
  bodyText: string;
  wordCount: number;
}

export interface UploadedFile {
  id: string;
  name: string;
  sizeBytes: number;
  mimeType: string;
  content: string;
}

export interface BillingPlan {
  plan_id: string;
  code: string;
  tier: string;
  monthly_fee: string;
  included_units: number;
  overage_rate: string;
}

export interface BillingTenant {
  tenantId: string;
  name: string;
  plan: BillingPlan;
  startsOn: string;
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

type CreateDocumentOptions = {
  title?: string;
  content?: string;
};

type UploadFileOptions = {
  name?: string;
  content?: string;
  mimeType?: string;
  owner?: Customer;
};

type Fixtures = {
  account: Account;
  customer: Customer;
  secondCustomer: Customer;
  newCustomerDetails: CustomerDetails;
  registerCustomer: (label?: string) => Promise<Customer>;
  createDocument: (options?: string | CreateDocumentOptions) => Promise<CustomerDocument>;
  uploadFile: (options?: string | UploadFileOptions) => Promise<UploadedFile>;
  shareFile: (from: Customer, to: Customer) => Promise<UploadedFile>;
  customerDocument: CustomerDocument;
  customerFile: UploadedFile;
  uploadedFile: UploadedFile;
  sharedFile: UploadedFile;
  trashedFile: UploadedFile;
  starredFile: UploadedFile;
  starredDocument: CustomerDocument;
  searchableDocument: SearchableDocument;
  sharedFileNotification: SharedFileNotification;
  billingTenant: BillingTenant;
  waitForSearchHit: (query: string, documentId: string, owner?: Customer) => Promise<void>;
  waitForNotification: (fileId: string, recipient?: Customer) => Promise<string>;
  customerPage: Page;
  runId: string;
};

type WorkerFixtures = {
  api: APIRequestContext;
  billingApi: APIRequestContext;
  billingPlans: BillingPlan[];
};

function bearer(customer: Customer) {
  return { Authorization: `Bearer ${customer.accessToken}` };
}

export function uniqueCustomerDetails(label = "Customer"): CustomerDetails {
  const suffix = randomUUID();
  return {
    displayName: `Smoke ${label} ${suffix.slice(0, 8)}`,
    email: `smoke-${suffix}@otterworks.test`,
    password: `Passw0rd!${suffix.slice(0, 8)}`,
  };
}

export async function registerCustomerViaApi(
  api: APIRequestContext,
  details: CustomerDetails = uniqueCustomerDetails(),
): Promise<Customer> {
  const response = await api.post("/api/v1/auth/register", { data: details });
  expect(response.status(), `register ${details.email}`).toBe(201);
  const body = await response.json();
  const customer: Customer = {
    ...details,
    id: String(body.user.id),
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
  };

  const profile = await api.get("/api/v1/auth/profile", { headers: bearer(customer) });
  expect(profile.status(), `profile ${details.email}`).toBe(200);
  expect(await profile.json()).toMatchObject({
    id: customer.id,
    email: customer.email,
    displayName: customer.displayName,
  });

  return customer;
}

export async function loginStatusViaApi(
  api: APIRequestContext,
  credentials: Pick<CustomerDetails, "email" | "password">,
): Promise<number> {
  const response = await api.post("/api/v1/auth/login", { data: credentials });
  return response.status();
}

export async function expectSignedInDashboard(page: Page, who: CustomerDetails) {
  await expect(page).toHaveURL(/\/dashboard$/);
  await expect(page.getByRole("heading", { name: "Dashboard", level: 1 })).toBeVisible();
  const profile = page.getByRole("complementary");
  await expect(profile.getByText(who.email, { exact: true })).toBeVisible();
  await expect(profile.getByText(who.displayName, { exact: true })).toBeVisible();
}

function localStorageState(baseURL: string | undefined, customer: Customer): StorageState {
  return {
    cookies: [],
    origins: [
      {
        origin: new URL(baseURL ?? "http://localhost:3000").origin,
        localStorage: [
          { name: ACCESS_TOKEN_KEY, value: customer.accessToken },
          { name: REFRESH_TOKEN_KEY, value: customer.refreshToken },
        ],
      },
    ],
  };
}

function sharedCustomerFromFiles(): Customer {
  const details = JSON.parse(readFileSync(AUTH_META_FILE, "utf8")) as CustomerDetails & {
    id: string;
  };
  const state = JSON.parse(readFileSync(AUTH_STATE_FILE, "utf8")) as StorageState;
  const localStorage = state.origins[0]?.localStorage ?? [];
  const accessToken = localStorage.find((item) => item.name === ACCESS_TOKEN_KEY)?.value;
  const refreshToken = localStorage.find((item) => item.name === REFRESH_TOKEN_KEY)?.value;
  if (!accessToken || !refreshToken) {
    throw new Error("Shared Playwright auth state is missing its access or refresh token.");
  }
  return { ...details, accessToken, refreshToken };
}

function mockCustomer(): Customer {
  return {
    id: "playwright-mock-user",
    displayName: "Playwright Mock",
    email: "playwright-mock@otterworks.test",
    password: "not-used",
    accessToken: "playwright-mock-access-token",
    refreshToken: "playwright-mock-refresh-token",
  };
}

export function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export const test = base.extend<Fixtures, WorkerFixtures>({
  account: ["shared", { option: true }],

  api: [
    async ({ playwright }, use) => {
      const api = await playwright.request.newContext({ baseURL: API_GATEWAY_URL });
      await use(api);
      await api.dispose();
    },
    { scope: "worker" },
  ],

  billingApi: [
    async ({ playwright }, use) => {
      const api = await playwright.request.newContext({
        baseURL: process.env.BASE_URL ?? "http://localhost:3000",
      });
      await use(api);
      await api.dispose();
    },
    { scope: "worker" },
  ],

  billingPlans: [
    async ({ billingApi }, use) => {
      const response = await billingApi.get("/billing-api/api/plans");
      expect(response.status(), "billing catalogue request").toBe(200);
      const plans = (await response.json()) as BillingPlan[];
      expect(plans.length, "billing catalogue must be seeded before Playwright tests").toBeGreaterThan(0);
      await use(plans);
    },
    { scope: "worker" },
  ],

  registerCustomer: async ({ api }, use) => {
    await use((label) => registerCustomerViaApi(api, uniqueCustomerDetails(label)));
  },

  newCustomerDetails: async ({}, use) => {
    await use(uniqueCustomerDetails("New"));
  },

  customer: async ({ account, registerCustomer }, use) => {
    if (account === "signedOut") {
      await use(mockCustomer());
    } else if (account === "fresh") {
      await use(await registerCustomer("Fresh"));
    } else if (process.env.PLAYWRIGHT_MOCK_AUTH === "1") {
      await use(mockCustomer());
    } else {
      await use(sharedCustomerFromFiles());
    }
  },

  storageState: async ({ account, customer, baseURL }, use) => {
    if (account === "signedOut") {
      await use({ cookies: [], origins: [] });
    } else if (account === "shared" && process.env.PLAYWRIGHT_MOCK_AUTH !== "1") {
      await use(AUTH_STATE_FILE);
    } else {
      await use(localStorageState(baseURL, customer));
    }
  },

  secondCustomer: async ({ registerCustomer }, use) => {
    await use(await registerCustomer("Second"));
  },

  createDocument: async ({ api, customer }, use) => {
    await use(async (input) => {
      const options = typeof input === "string" ? { title: input } : (input ?? {});
      const suffix = randomUUID();
      const title = `${options.title ?? "Smoke document"}-${suffix.slice(0, 8)}`;
      const content = options.content ?? `Playwright document fixture ${suffix}`;
      const response = await api.post("/api/v1/documents", {
        headers: bearer(customer),
        data: { title, content, content_type: "text/plain" },
      });
      expect(response.status(), "create document").toBe(201);
      const body = await response.json();
      return {
        id: String(body.id),
        title,
        bodyText: content,
        wordCount: content.trim().split(/\s+/).filter(Boolean).length,
      };
    });
  },

  uploadFile: async ({ api, customer }, use) => {
    await use(async (input) => {
      const options = typeof input === "string" ? { name: input } : (input ?? {});
      const suffix = randomUUID();
      const name = options.name ?? `smoke-file-${suffix}.txt`;
      const content = options.content ?? `Playwright file fixture ${suffix}\n`;
      const mimeType = options.mimeType ?? "text/plain";
      const owner = options.owner ?? customer;
      const response = await api.post("/api/v1/files/upload", {
        headers: bearer(owner),
        multipart: {
          file: { name, mimeType, buffer: Buffer.from(content) },
          owner_id: owner.id,
        },
      });
      expect(response.status(), "upload file").toBe(201);
      const body = await response.json();
      return {
        id: String(body.file.id),
        name: String(body.file.name),
        sizeBytes: Buffer.byteLength(content),
        mimeType,
        content,
      };
    });
  },

  shareFile: async ({ api, uploadFile }, use) => {
    await use(async (from, to) => {
      const file = await uploadFile({ owner: from, name: `shared-${randomUUID()}.txt` });
      const response = await api.post(`/api/v1/files/${file.id}/share`, {
        headers: bearer(from),
        data: { shared_with: to.id, permission: "viewer", shared_by: from.id },
      });
      expect(response.status(), "share new file").toBe(201);
      return file;
    });
  },

  customerDocument: async ({ createDocument }, use) => {
    await use(await createDocument({ title: "Customer document" }));
  },

  customerFile: async ({ uploadFile }, use) => {
    await use(await uploadFile());
  },

  uploadedFile: async ({ uploadFile }, use) => {
    await use(await uploadFile());
  },

  sharedFile: async ({ shareFile, secondCustomer, customer }, use) => {
    await use(await shareFile(secondCustomer, customer));
  },

  trashedFile: async ({ api, customer, uploadFile }, use) => {
    const file = await uploadFile({ name: `trashed-${randomUUID()}.txt` });
    const response = await api.post(`/api/v1/files/${file.id}/trash`, {
      headers: bearer(customer),
    });
    expect(response.ok(), "move newly uploaded file to trash").toBe(true);
    await use(file);
  },

  starredFile: async ({ page, uploadFile }, use) => {
    const file = await uploadFile({ name: `starred-${randomUUID()}.txt` });
    await page.goto("/files");
    const main = page.getByRole("main");
    const link = main.getByRole("link", { name: new RegExp(escapeRegExp(file.name)) });
    await expect(link).toBeVisible();
    const row = link.locator("xpath=..");
    await row.getByRole("button", { name: "Star", exact: true }).click();
    await expect(row.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
    await use(file);
  },

  starredDocument: async ({ page, createDocument }, use) => {
    const document = await createDocument({ title: "Starred document" });
    await page.goto("/documents");
    const main = page.getByRole("main");
    const link = main.getByRole("link", { name: new RegExp(escapeRegExp(document.title)) });
    await expect(link).toBeVisible();
    await link.getByRole("button", { name: "Star", exact: true }).click();
    await expect(link.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
    await use(document);
  },

  waitForSearchHit: async ({ api, customer }, use) => {
    await use(async (query, documentId, owner = customer) => {
      await expect
        .poll(
          async () => {
            const response = await api.get("/api/v1/search", {
              headers: bearer(owner),
              params: { q: query },
            });
            if (!response.ok()) return [];
            const body = await response.json();
            return (body.results ?? []).map((result: { id: string }) => String(result.id));
          },
          { message: "document reaches the search index", timeout: SEARCH_INDEX_TIMEOUT },
        )
        .toContain(String(documentId));
    });
  },

  searchableDocument: async ({ createDocument, waitForSearchHit }, use) => {
    const searchTerm = `otterquarry${randomUUID().replace(/-/g, "").slice(0, 12)}`;
    const document = await createDocument({
      title: `Smoke search ${searchTerm}`,
      content: `Quarterly planning notes mentioning ${searchTerm}.`,
    });
    await waitForSearchHit(searchTerm, document.id);
    await use({ id: document.id, title: document.title, searchTerm });
  },

  waitForNotification: async ({ api, customer }, use) => {
    await use(async (fileId, recipient = customer) => {
      let notificationId = "";
      await expect
        .poll(
          async () => {
            const response = await api.get("/api/v1/notifications", {
              headers: bearer(recipient),
            });
            if (!response.ok()) return "";
            const body = await response.json();
            const match = (body.data ?? []).find(
              (notification: { resourceId?: string }) => notification.resourceId === fileId,
            );
            notificationId = match?.id ?? "";
            return notificationId;
          },
          { message: "shared-file notification is delivered", timeout: NOTIFICATION_DELIVERY_TIMEOUT },
        )
        .not.toBe("");
      return notificationId;
    });
  },

  sharedFileNotification: async ({ customer, secondCustomer, shareFile, waitForNotification }, use) => {
    const file = await shareFile(secondCustomer, customer);
    const notificationId = await waitForNotification(file.id, customer);
    await use({
      notificationId,
      fileId: file.id,
      fileName: file.name,
      sharer: secondCustomer,
    });
  },

  billingTenant: async ({ billingApi, billingPlans }, use) => {
    const tenantId = randomUUID();
    const name = `playwright-billing-${tenantId}`;
    execFileSync(
      "docker",
      [
        "exec",
        BILLING_DB_CONTAINER,
        "psql",
        "-U",
        "billing_svc",
        "-d",
        "billing_svc_dev",
        "-v",
        "ON_ERROR_STOP=1",
        "-c",
        `INSERT INTO billing_svc.tenants (id, name, tax_exempt, status) VALUES ('${tenantId}', '${name}', false, 'active');`,
      ],
      { stdio: "pipe" },
    );
    const plan = billingPlans[0];
    const startsOn = "2026-01-01";
    const response = await billingApi.post(`/billing-api/api/tenants/${tenantId}/plan-change`, {
      data: { plan_id: plan.plan_id, effective_on: startsOn },
    });
    expect(response.status(), "create plan for this fixture tenant").toBe(200);
    expect(await response.json()).toMatchObject({
      latest_plan: plan.plan_id,
      latest_start: startsOn,
    });
    await use({ tenantId, name, plan, startsOn });
  },

  customerPage: async ({ page }, use) => {
    await use(page);
  },

  runId: async ({}, use) => {
    await use(randomUUID());
  },
});

export { expect };
