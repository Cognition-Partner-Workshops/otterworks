import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type SeededDocument = { id: string; title: string };

export const test = base.extend<{ seededDocument: SeededDocument }>({
  seededDocument: async ({ page, request }, use) => {
    const unique = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: {
        displayName: "Documents Smoke",
        email: `documents-smoke-${unique}@example.com`,
        password: "Documents-Smoke-2026!",
      },
    });
    await expect(registration).toBeOK();
    const tokens = await registration.json();

    const created = await request.post("/api/v1/documents", {
      headers: { Authorization: `Bearer ${tokens.accessToken}` },
      data: { title: `Smoke document ${unique}`, content: "Seeded by the documents smoke test." },
    });
    await expect(created).toBeOK();
    const document: SeededDocument = await created.json();

    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);

    await use(document);
  },
});

export { expect };
