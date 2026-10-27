import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type TrashedFile = { name: string };

export const test = base.extend<{ trashedFile: TrashedFile }>({
  trashedFile: async ({ page, request }, use) => {
    const suffix = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: {
        displayName: "Trash Smoke",
        email: `trash-smoke-${suffix}@example.com`,
        password: "Trash-Smoke-2026!",
      },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken, user } = await registration.json();
    const headers = { Authorization: `Bearer ${accessToken}` };

    const name = `trash-smoke-${suffix}.txt`;
    const upload = await request.post("/api/v1/files/upload", {
      headers,
      multipart: {
        file: { name, mimeType: "text/plain", buffer: Buffer.from("trash smoke") },
        owner_id: user.id,
      },
    });
    await expect(upload).toBeOK();
    const { file } = await upload.json();
    await expect(await request.post(`/api/v1/files/${file.id}/trash`, { headers })).toBeOK();

    const trash = await request.get("/api/v1/files/trash", {
      headers,
      params: { owner_id: user.id },
    });
    await expect(trash).toBeOK();
    expect((await trash.json()).files).toEqual([expect.objectContaining({ id: file.id, name })]);

    await page.addInitScript(
      (tokens) => {
        localStorage.setItem("otter_access_token", tokens.accessToken);
        localStorage.setItem("otter_refresh_token", tokens.refreshToken);
      },
      { accessToken, refreshToken },
    );
    await use({ name });
  },
});

export { expect };
