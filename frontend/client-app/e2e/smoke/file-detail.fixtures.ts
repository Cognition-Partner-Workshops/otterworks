import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type UploadedTextFile = { id: string; name: string; content: string };

export const test = base.extend<{ uploadedTextFile: UploadedTextFile }>({
  uploadedTextFile: async ({ request, page }, use) => {
    const runId = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: {
        displayName: "File Detail Smoke",
        email: `file-detail-${runId}@example.com`,
        password: "File-Detail-Smoke-2026!",
      },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken } = await registration.json();

    const name = `smoke-file-detail-${runId}.txt`;
    const content = `File detail smoke ${runId}`;
    const upload = await request.post("/api/v1/files/upload", {
      headers: { Authorization: `Bearer ${accessToken}` },
      multipart: { file: { name, mimeType: "text/plain", buffer: Buffer.from(content) } },
    });
    await expect(upload).toBeOK();
    const { file } = await upload.json();

    await page.addInitScript(
      (tokens) => {
        localStorage.setItem("otter_access_token", tokens.accessToken);
        localStorage.setItem("otter_refresh_token", tokens.refreshToken);
      },
      { accessToken, refreshToken },
    );
    await use({ id: file.id, name, content });
  },
});

export { expect };
