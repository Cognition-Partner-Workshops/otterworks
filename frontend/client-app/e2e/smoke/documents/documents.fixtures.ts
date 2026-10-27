/* eslint-disable react-hooks/rules-of-hooks -- Playwright fixture `use` callbacks are not React hooks. */
import { randomUUID } from "node:crypto";
import { test as base, expect, type Page } from "@playwright/test";

type Customer = {
  id: string;
  email: string;
  password: string;
  displayName: string;
  accessToken: string;
  refreshToken: string;
};

type CustomerDocument = {
  id: string;
  title: string;
  bodyText: string;
  wordCount: number;
};

type DocumentFixtures = {
  customer: Customer;
  customerPage: Page;
  createDocument: (label: string) => Promise<CustomerDocument>;
  customerDocument: CustomerDocument;
};

export const test = base.extend<DocumentFixtures>({
  customer: async ({ request }, use) => {
    const uuid = randomUUID();
    const email = `smoke-docs-${uuid}@otterworks.test`;
    const password = `Smoke-${uuid.slice(0, 8)}-9a`;
    const displayName = `Smoke Docs ${uuid.slice(0, 8)}`;
    const registerResponse = await request.post("/api/v1/auth/register", {
      data: { email, password, displayName },
    });

    expect(registerResponse.status()).toBe(201);
    const auth = await registerResponse.json();
    const profileResponse = await request.get("/api/v1/auth/profile", {
      headers: { Authorization: `Bearer ${auth.accessToken}` },
    });

    expect(profileResponse.status()).toBe(200);
    const profile = await profileResponse.json();

    await use({
      id: profile.id,
      email,
      password,
      displayName,
      accessToken: auth.accessToken,
      refreshToken: auth.refreshToken,
    });
  },

  customerPage: async ({ page, customer }, use) => {
    await page.addInitScript(({ accessToken, refreshToken }) => {
      const seededFlag = "otter_smoke_docs_tokens_seeded";

      if (sessionStorage.getItem(seededFlag)) {
        return;
      }

      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
      sessionStorage.setItem(seededFlag, "true");
    }, {
      accessToken: customer.accessToken,
      refreshToken: customer.refreshToken,
    });

    await use(page);
  },

  createDocument: async ({ request, customer }, use) => {
    await use(async (label: string) => {
      const uuid = randomUUID();
      const title = `${label} ${uuid}`;
      const bodyText = `Smoke body ${uuid}`;
      const response = await request.post("/api/v1/documents", {
        headers: { Authorization: `Bearer ${customer.accessToken}` },
        data: { title, content: `<p>${bodyText}</p>` },
      });

      expect(response.status()).toBe(201);
      const document = await response.json();

      return {
        id: document.id,
        title,
        bodyText,
        wordCount: document.word_count,
      };
    });
  },

  customerDocument: async ({ createDocument }, use) => {
    await use(await createDocument("Smoke document"));
  },
});

export { expect };
