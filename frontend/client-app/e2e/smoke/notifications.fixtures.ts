import { test as base, expect, type APIRequestContext } from "@playwright/test";

type Account = { id: string; accessToken: string; refreshToken: string };

export type SharedFileNotification = {
  /** The signed-in customer who receives the notification. */
  customer: Account;
  /** The other user who shared a file with the customer (appears in the message). */
  sharerId: string;
  fileId: string;
};

function uniqueLabel(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

async function registerAccount(request: APIRequestContext, prefix: string): Promise<Account> {
  const label = uniqueLabel(prefix);
  const response = await request.post("/api/v1/auth/register", {
    data: { email: `${label}@otterworks.test`, password: "Passw0rd!23", displayName: label },
  });
  expect(response.status(), await response.text()).toBe(201);
  const body = await response.json();
  return { id: body.user.id, accessToken: body.accessToken, refreshToken: body.refreshToken };
}

/** Sharer uploads a file and shares it with the customer through file-service (emits file_shared). */
async function shareFile(request: APIRequestContext, sharer: Account, recipientId: string): Promise<string> {
  const headers = { Authorization: `Bearer ${sharer.accessToken}` };
  const upload = await request.post("/api/v1/files/upload", {
    headers,
    multipart: {
      file: { name: `${uniqueLabel("smoke")}.txt`, mimeType: "text/plain", buffer: Buffer.from("notifications smoke") },
      owner_id: sharer.id,
    },
  });
  expect(upload.ok(), await upload.text()).toBe(true);
  const fileId: string = (await upload.json()).file.id;

  const share = await request.post(`/api/v1/files/${fileId}/share`, {
    headers,
    data: { shared_with: recipientId, permission: "viewer", shared_by: sharer.id },
  });
  expect(share.status(), await share.text()).toBe(201);
  return fileId;
}

export const test = base.extend<{ sharedFileNotification: SharedFileNotification }>({
  sharedFileNotification: async ({ request, page }, use) => {
    const customer = await registerAccount(request, "notif-customer");
    const sharer = await registerAccount(request, "notif-sharer");
    const fileId = await shareFile(request, sharer, customer.id);

    // SNS -> SQS -> notification-service is asynchronous: poll the real API until it lands.
    await expect
      .poll(async () => {
        const response = await request.get("/api/v1/notifications", {
          headers: { Authorization: `Bearer ${customer.accessToken}` },
        });
        const body = await response.json();
        return (body.data ?? []).some((n: { resourceId?: string }) => n.resourceId === fileId);
      }, { timeout: 30_000 })
      .toBe(true);

    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, customer);

    await use({ customer, sharerId: sharer.id, fileId });
  },
});

export { expect };
