import { randomUUID } from "node:crypto";
import { test as base, expect, type APIRequestContext } from "@playwright/test";

const API_GATEWAY_URL = process.env.API_GATEWAY_URL ?? "http://localhost:8080";
const API = `${API_GATEWAY_URL}/api/v1`;

export type Customer = {
  id: string;
  email: string;
  password: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
};

export type UploadedFile = {
  id: string;
  name: string;
  mimeType: string;
  content: string;
  sizeBytes: number;
};

type FilesFixtures = {
  /** A brand-new customer registered through the API gateway; `page` starts signed in as them. */
  customer: Customer;
  /** A text file the signed-in customer uploaded through the API gateway. */
  uploadedFile: UploadedFile;
};

async function registerCustomer(request: APIRequestContext): Promise<Customer> {
  const suffix = randomUUID();
  const email = `smoke-files-${suffix}@otterworks.test`;
  const password = `Smoke-${suffix.slice(0, 12)}!`;
  const displayName = `Files Smoke ${suffix.slice(0, 8)}`;

  const response = await request.post(`${API}/auth/register`, {
    data: { email, password, displayName },
  });
  expect(response.status(), await response.text()).toBe(201);
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

export const test = base.extend<FilesFixtures>({
  customer: async ({ page, request }, use) => {
    const customer = await registerCustomer(request);
    await page.addInitScript(
      ({ accessToken, refreshToken }) => {
        localStorage.setItem("otter_access_token", accessToken);
        localStorage.setItem("otter_refresh_token", refreshToken);
      },
      { accessToken: customer.accessToken, refreshToken: customer.refreshToken },
    );
    await use(customer);
  },

  uploadedFile: async ({ customer, request }, use) => {
    const suffix = randomUUID();
    const name = `smoke-file-${suffix}.txt`;
    const content = `OtterWorks files smoke ${suffix}`;
    const mimeType = "text/plain";

    const response = await request.post(`${API}/files/upload`, {
      headers: { Authorization: `Bearer ${customer.accessToken}` },
      multipart: {
        file: { name, mimeType, buffer: Buffer.from(content) },
      },
    });
    expect(response.status(), await response.text()).toBe(201);
    const { file } = await response.json();

    await use({
      id: file.id,
      name,
      mimeType,
      content,
      sizeBytes: Buffer.byteLength(content),
    });
  },
});

export { expect };
