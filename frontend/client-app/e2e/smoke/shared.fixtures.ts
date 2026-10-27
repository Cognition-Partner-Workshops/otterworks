import { randomUUID } from "node:crypto";
import { test as base, expect, type APIRequestContext } from "@playwright/test";

type Account = { accessToken: string; refreshToken: string; user: { id: string } };

async function registerCustomer(request: APIRequestContext, role: string): Promise<Account> {
  const name = `smoke-shared-${role}-${randomUUID()}`;
  const response = await request.post("/api/v1/auth/register", {
    data: { displayName: name, email: `${name}@example.test`, password: "Smoke-Shared-2026!" },
  });
  await expect(response).toBeOK();
  return response.json();
}

/** Registers a fresh owner and recipient, uploads a file as the owner, shares it with the recipient,
 *  and signs the browser in as the recipient (tokens in localStorage before any page script runs). */
export const test = base.extend<{ sharedFileName: string }>({
  sharedFileName: async ({ request, page }, use) => {
    const recipient = await registerCustomer(request, "recipient");
    const owner = await registerCustomer(request, "owner");
    const headers = { Authorization: `Bearer ${owner.accessToken}` };
    const fileName = `shared-smoke-${randomUUID()}.txt`;

    const upload = await request.post("/api/v1/files/upload", {
      headers,
      multipart: {
        owner_id: owner.user.id,
        file: { name: fileName, mimeType: "text/plain", buffer: Buffer.from("shared smoke fixture\n") },
      },
    });
    await expect(upload).toBeOK();
    const { file } = await upload.json();

    const share = await request.post(`/api/v1/files/${file.id}/share`, {
      headers,
      data: { shared_with: recipient.user.id, shared_by: owner.user.id, permission: "viewer" },
    });
    await expect(share).toBeOK();

    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, recipient);
    await use(fileName);
  },
});
export { expect } from "@playwright/test";
