import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type RecentDocument = { id: string; title: string };

export const test = base.extend<{ recentDocument: RecentDocument }>({
  recentDocument: async ({ request, page }, use) => {
    const unique = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: { displayName: "Recent Smoke", email: `recent-smoke-${unique}@example.com`, password: "Smoke-Test-2026!" },
    });
    await expect(registration).toBeOK();
    const { accessToken, refreshToken } = await registration.json();
    const created = await request.post("/api/v1/documents", {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: { title: `Recent smoke ${unique}`, content: "Edited just now." },
    });
    await expect(created).toBeOK();
    const document: RecentDocument = await created.json();
    await page.addInitScript((tokens) => {
      localStorage.setItem("otter_access_token", tokens.accessToken);
      localStorage.setItem("otter_refresh_token", tokens.refreshToken);
    }, { accessToken, refreshToken });
    await use({ id: document.id, title: document.title });
  },
});

export { expect };
