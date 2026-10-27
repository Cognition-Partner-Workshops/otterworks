import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type StarredDocument = { id: string; title: string };

export const test = base.extend<{ starredDocument: StarredDocument }>({
  starredDocument: async ({ page, request }, use) => {
    const runId = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: { displayName: "Starred Smoke", email: `starred-${runId}@example.com`, password: "Starred-Test-2026!" },
    });
    await expect(registration).toBeOK();
    const tokens = await registration.json();
    const headers = { Authorization: `Bearer ${tokens.accessToken}` };

    const profile = await request.get("/api/v1/auth/profile", { headers });
    await expect(profile).toBeOK();
    const { id: userId } = await profile.json();

    const created = await request.post("/api/v1/documents", {
      headers,
      data: { title: `Starred smoke ${runId}`, content: "Seeded for the /starred smoke test." },
    });
    await expect(created).toBeOK();
    const document: StarredDocument = await created.json();

    // Stars have no HTTP API: the client keeps them in localStorage (starredApi in src/lib/api.ts).
    await page.addInitScript(({ accessToken, refreshToken, userId, documentId }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
      localStorage.setItem(
        "otter_starred_items",
        JSON.stringify({ [`${userId}:${documentId}`]: { itemId: documentId, itemType: "document", starredAt: new Date().toISOString() } }),
      );
    }, { accessToken: tokens.accessToken, refreshToken: tokens.refreshToken, userId, documentId: document.id });

    await use(document);
  },
});

export { expect };
