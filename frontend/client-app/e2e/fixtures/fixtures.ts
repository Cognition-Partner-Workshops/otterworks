import { randomUUID } from "node:crypto";
import { readFile } from "node:fs/promises";
import {
  test as base,
  expect,
  request as playwrightRequest,
  type APIRequestContext,
  type TestInfo,
} from "@playwright/test";
import type { Entitlement } from "../../src/features/billing/api";
import {
  registerAccount,
  SHARED_CUSTOMER_META,
  signedOut,
  storageStateFor,
  uniqueIdentity,
  type Account,
} from "./accounts";
import {
  BILLING_TENANTS,
  ENTITLEMENT_DATE,
  getBillingCatalog,
  uniqueEffectiveOn,
  type CatalogPlan,
} from "./billing";
import {
  createDocument,
  deleteDocument,
  shareFile,
  starredItemsScript,
  trashFile,
  uploadTextFile,
  waitForNotification,
  waitUntilIndexed,
  type SeededDocument,
  type SeededFile,
} from "./seed";

// The shared customer must never log out, call /auth/refresh, change password
// or profile (profile Save PATCH /auth/profile is a known 500 defect), empty
// trash, or mark notifications read; tests that need that use
// `test.use({ freshCustomer: true })`.
type TestFixtures = {
  request: APIRequestContext;
  freshCustomer: boolean;
  customer: Account;
  document: SeededDocument;
  searchableDocument: SeededDocument & { keyword: string };
  starredDocument: SeededDocument;
  textFile: SeededFile;
  trashedFile: SeededFile;
  sharedFile: SeededFile & { owner: Account };
  fileShareNotification: { fileId: string; sharerId: string };
  billingCatalog: CatalogPlan[];
  tenantEntitlement: Entitlement;
  planChange: { tenantId: string; planCode: string; effectiveOn: string };
};

type WorkerFixtures = { sharedCustomer: Account };

function pageSlug(testInfo: TestInfo): string {
  return (
    testInfo.tags
      .find((tag) => tag.startsWith("@page-"))
      ?.slice("@page-".length) ?? "customer"
  );
}

export const test = base.extend<TestFixtures, WorkerFixtures>({
  // The default request failed with "Invalid URL" once storageState was overridden.
  request: async ({ baseURL }, use) => {
    const context = await playwrightRequest.newContext({ baseURL });
    await use(context);
    await context.dispose();
  },
  sharedCustomer: [
    async ({}, use) => {
      let account: Account;
      try {
        account = JSON.parse(
          await readFile(SHARED_CUSTOMER_META, "utf8"),
        ) as Account;
      } catch {
        throw new Error(
          "Shared customer not found: run through the 'chromium' project so the 'setup' project runs first (no --no-deps)",
        );
      }
      await use(account);
    },
    { scope: "worker" },
  ],
  freshCustomer: [false, { option: true }],
  customer: async (
    { freshCustomer, sharedCustomer, request },
    use,
    testInfo,
  ) => {
    await use(
      freshCustomer
        ? await registerAccount(request, pageSlug(testInfo))
        : sharedCustomer,
    );
  },
  storageState: async (
    { storageState, freshCustomer, customer, baseURL },
    use,
  ) => {
    await use(
      freshCustomer ? storageStateFor(customer, baseURL!) : storageState,
    );
  },
  document: async ({ request, customer }, use) => {
    const document = await createDocument(request, customer);
    await use(document);
    await deleteDocument(request, customer, document.id);
  },
  searchableDocument: async ({ request, customer }, use) => {
    const keyword = `otterscope${randomUUID().slice(0, 8)}`;
    const document = await createDocument(request, customer, {
      title: `Smoke ${keyword} Brief`,
      text: `Search smoke document ${keyword}.`,
    });
    await waitUntilIndexed(request, customer, keyword, document.id);
    await use({ ...document, keyword });
    await deleteDocument(request, customer, document.id);
  },
  starredDocument: async ({ request, context, customer }, use) => {
    const document = await createDocument(request, customer);
    await context.addInitScript(starredItemsScript, {
      userId: customer.id,
      documentId: document.id,
    });
    await use(document);
    await deleteDocument(request, customer, document.id);
  },
  textFile: async ({ request, customer }, use) => {
    await use(await uploadTextFile(request, customer));
  },
  trashedFile: async ({ request, customer }, use) => {
    const file = await uploadTextFile(request, customer);
    await trashFile(request, customer, file.id);
    await use(file);
  },
  sharedFile: async ({ request, customer }, use, testInfo) => {
    const owner = await registerAccount(request, `${pageSlug(testInfo)}-owner`);
    const file = await uploadTextFile(request, owner);
    await shareFile(request, owner, file.id, customer);
    await use({ ...file, owner });
  },
  fileShareNotification: async ({ request, customer, sharedFile }, use) => {
    await waitForNotification(request, customer, sharedFile.id);
    await use({ fileId: sharedFile.id, sharerId: sharedFile.owner.id });
  },
  billingCatalog: async ({ request }, use) => {
    const catalog = await getBillingCatalog(request);
    expect(
      catalog.length,
      "billing catalog empty: the setup project seeds it",
    ).toBeGreaterThan(0);
    await use(catalog);
  },
  tenantEntitlement: async ({ request }, use) => {
    const response = await request.get(
      `/billing-api/api/tenants/${BILLING_TENANTS.entitlement}/entitlement?on=${ENTITLEMENT_DATE}`,
    );
    await expect(response).toBeOK();
    await use((await response.json()) as Entitlement);
  },
  planChange: async ({ billingCatalog }, use) => {
    expect(billingCatalog.map(({ code }) => code)).toContain("GROWTH");
    await use({
      tenantId: BILLING_TENANTS.planChange,
      planCode: "GROWTH",
      effectiveOn: uniqueEffectiveOn(),
    });
  },
});

export {
  expect,
  uniqueIdentity,
  signedOut,
  BILLING_TENANTS,
  ENTITLEMENT_DATE,
};
