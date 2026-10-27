/* eslint-disable react-hooks/rules-of-hooks -- Playwright fixture callbacks name their provider `use`; they are not React hooks. */
import { randomUUID } from "node:crypto";
import {
  test as base,
  expect,
  type APIRequestContext,
} from "@playwright/test";

/** A customer registered through the real auth-service (via the API gateway). */
export type Customer = {
  id: string;
  email: string;
  password: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
};

/** A file stored in file-service. */
export type StoredFile = { id: string; name: string };

/** A document stored in document-service. */
export type StoredDocument = { id: string; title: string };

type CollectionsFixtures = {
  /** API client for the real API gateway, reached through the app's /api/v1 proxy. */
  api: APIRequestContext;
  /** Fresh customer the page is opened as (signed in through `storageState`). */
  customer: Customer;
  /** Second fresh customer who owns and shares files with `customer`. */
  sharer: Customer;
  /** File uploaded by `sharer` and shared with `customer` as viewer. */
  sharedFile: StoredFile;
  /** File uploaded by `customer` and moved to trash. */
  trashedFile: StoredFile;
  /** File uploaded by `customer` and starred from the Files page. */
  starredFile: StoredFile;
  /** Document created by `customer` and starred from the Documents page. */
  starredDocument: StoredDocument;
};

const API = "/api/v1";
const PASSWORD = "Passw0rd!23";

export const uniqueName = (prefix: string) => `${prefix}-${randomUUID()}`;

const bearer = (customer: Customer) => ({
  Authorization: `Bearer ${customer.accessToken}`,
});

async function registerCustomer(
  request: APIRequestContext,
  label: string,
): Promise<Customer> {
  const suffix = randomUUID();
  const email = `smoke-collections-${label}-${suffix}@otterworks.test`;
  const displayName = `Smoke ${label} ${suffix.slice(0, 8)}`;

  const register = await request.post(`${API}/auth/register`, {
    data: { email, password: PASSWORD, displayName },
  });
  expect(register.status(), await register.text()).toBe(201);
  const tokens = (await register.json()) as {
    accessToken: string;
    refreshToken: string;
  };

  const profile = await request.get(`${API}/auth/profile`, {
    headers: { Authorization: `Bearer ${tokens.accessToken}` },
  });
  expect(profile.status(), await profile.text()).toBe(200);
  const { id } = (await profile.json()) as { id: string };

  return {
    id,
    email,
    password: PASSWORD,
    displayName,
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken,
  };
}

async function uploadFile(
  request: APIRequestContext,
  owner: Customer,
  name: string,
): Promise<StoredFile> {
  const response = await request.post(`${API}/files/upload`, {
    headers: bearer(owner),
    multipart: {
      file: {
        name,
        mimeType: "text/plain",
        buffer: Buffer.from(`OtterWorks smoke fixture ${name}\n`),
      },
      owner_id: owner.id,
    },
  });
  expect(response.ok(), await response.text()).toBe(true);
  const { file } = (await response.json()) as {
    file: { id: string; name: string };
  };
  expect(file.name).toBe(name);
  return { id: file.id, name: file.name };
}

export const test = base.extend<CollectionsFixtures>({
  api: async ({ playwright, baseURL }, use) => {
    const api = await playwright.request.newContext({ baseURL });
    await use(api);
    await api.dispose();
  },

  customer: async ({ api }, use) => {
    await use(await registerCustomer(api, "customer"));
  },

  // Sign the browser in as `customer` with the tokens the real auth-service issued,
  // stored under the same localStorage keys the login page writes.
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

  sharer: async ({ api }, use) => {
    await use(await registerCustomer(api, "sharer"));
  },

  sharedFile: async ({ api: request, sharer, customer }, use) => {
    const file = await uploadFile(
      request,
      sharer,
      `${uniqueName("smoke-shared")}.txt`,
    );
    const share = await request.post(`${API}/files/${file.id}/share`, {
      headers: bearer(sharer),
      data: {
        shared_with: customer.id,
        permission: "viewer",
        shared_by: sharer.id,
      },
    });
    expect(share.ok(), await share.text()).toBe(true);
    await use(file);
  },

  trashedFile: async ({ api: request, customer }, use) => {
    const file = await uploadFile(
      request,
      customer,
      `${uniqueName("smoke-trashed")}.txt`,
    );
    const trash = await request.post(`${API}/files/${file.id}/trash`, {
      headers: bearer(customer),
    });
    expect(trash.ok(), await trash.text()).toBe(true);
    await use(file);
  },

  // Stars live in the browser (localStorage `otter_starred_items`), so the star is
  // added the way a customer does it: the Star button on the Files page.
  starredFile: async ({ api: request, customer, page }, use) => {
    const file = await uploadFile(
      request,
      customer,
      `${uniqueName("smoke-starred")}.txt`,
    );
    await test.step(`Star file ${file.name} on /files`, async () => {
      await page.goto("/files");
      const main = page.getByRole("main");
      await expect(
        main.getByRole("link", { name: new RegExp(escapeRegExp(file.name)) }),
      ).toBeVisible();
      await main.getByRole("button", { name: "Star", exact: true }).click();
      await expect(
        main.getByRole("button", { name: "Unstar", exact: true }),
      ).toBeVisible();
    });
    await use(file);
  },

  starredDocument: async ({ api: request, customer, page }, use) => {
    const title = uniqueName("smoke-starred-doc");
    const response = await request.post(`${API}/documents`, {
      headers: bearer(customer),
      data: { title, content: "Starred smoke fixture" },
    });
    expect(response.status(), await response.text()).toBe(201);
    const { id } = (await response.json()) as { id: string };
    await test.step(`Star document ${title} on /documents`, async () => {
      await page.goto("/documents");
      const main = page.getByRole("main");
      await expect(
        main.getByRole("link", { name: new RegExp(escapeRegExp(title)) }),
      ).toBeVisible();
      await main.getByRole("button", { name: "Star", exact: true }).click();
      await expect(
        main.getByRole("button", { name: "Unstar", exact: true }),
      ).toBeVisible();
    });
    await use({ id, title });
  },
});

/** Signed-out browser state for tests that check anonymous behaviour. */
export const signedOut = { cookies: [], origins: [] };

export function escapeRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export { expect };
