import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type UploadedFile = { id: string; name: string };

export const test = base.extend<{ uploadedFile: UploadedFile }>({
  // Registers a unique customer through the real API, uploads one uniquely named
  // file as that customer, and signs the browser in with the issued tokens.
  uploadedFile: async ({ page, request }, use) => {
    const unique = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: {
        displayName: "Files Smoke",
        email: `files-smoke-${unique}@example.com`,
        password: "Files-Smoke-2026!",
      },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken, user } = await registration.json();

    const name = `files-smoke-${unique}.txt`;
    const upload = await request.post("/api/v1/files/upload", {
      headers: { Authorization: `Bearer ${accessToken}` },
      multipart: {
        file: { name, mimeType: "text/plain", buffer: Buffer.from("files page smoke test") },
        owner_id: user.id,
      },
    });
    await expect(upload).toBeOK();
    const body = await upload.json();
    const file = body.file ?? body;

    await page.addInitScript((tokens) => {
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
    }, { accessToken, refreshToken });

    await use({ id: file.id, name });
  },
});

export { expect };
