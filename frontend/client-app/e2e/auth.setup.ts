import { mkdir, writeFile } from "node:fs/promises";
import { dirname } from "node:path";
import { expect, test as setup } from "@playwright/test";
import {
  registerAccount,
  SHARED_CUSTOMER_META,
  SHARED_CUSTOMER_STATE,
  storageStateFor,
} from "./fixtures/accounts";
import { seedBillingCatalog } from "./fixtures/billing";

// Re-register every run because the access JWT lives 3600s and the client never
// refreshes; --no-deps/UI-mode reuse of a file older than 1h gives 401, clears
// the tokens, and redirects to /login.
setup("register the shared signed-in customer", async ({ request, baseURL }) => {
  const account = await registerAccount(request, "shared-customer");
  const profile = await request.get("/api/v1/auth/profile", {
    headers: account.headers,
  });
  await expect(profile).toBeOK();
  expect((await profile.json()).email).toBe(account.email);

  const payload = JSON.parse(
    Buffer.from(account.accessToken.split(".")[1], "base64url").toString(),
  ) as { exp: number };
  expect(payload.exp * 1000 - Date.now()).toBeGreaterThan(15 * 60_000);

  await mkdir(dirname(SHARED_CUSTOMER_STATE), { recursive: true });
  await writeFile(
    SHARED_CUSTOMER_STATE,
    JSON.stringify(storageStateFor(account, baseURL!), null, 2),
  );
  await writeFile(SHARED_CUSTOMER_META, JSON.stringify(account, null, 2));
});

setup("add billing fixture data without modifying existing rows", async ({
  request,
}) => {
  await seedBillingCatalog(request);
});
