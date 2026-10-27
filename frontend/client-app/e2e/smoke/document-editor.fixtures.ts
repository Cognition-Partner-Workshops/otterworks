import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

export type EditorDocument = { id: string; title: string; content: string };

export const test = base.extend<{ editorDocument: EditorDocument }>({
  editorDocument: async ({ request, page }, use) => {
    const runId = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: {
        displayName: "Editor Smoke",
        email: `editor-smoke-${runId}@example.com`,
        password: "Editor-Smoke-2026!",
      },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken } = await registration.json();
    const headers = { Authorization: `Bearer ${accessToken}` };

    const title = `Editor smoke ${runId}`;
    const content = `Smoke body ${runId}`;
    const created = await request.post("/api/v1/documents", {
      headers,
      data: { title, content: `<p>${content}</p>` },
    });
    await expect(created).toBeOK();
    const { id } = await created.json();

    await page.addInitScript((tokens) => {
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
    }, { accessToken, refreshToken });

    await use({ id, title, content });

    await expect(await request.delete(`/api/v1/documents/${id}`, { headers })).toBeOK();
  },
});

export { expect };
