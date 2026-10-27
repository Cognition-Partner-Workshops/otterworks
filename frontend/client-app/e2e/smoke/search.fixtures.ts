import { randomUUID } from "node:crypto";
import { test as base, expect } from "@playwright/test";

type SearchableDocument = { id: string; title: string; keyword: string };

export const test = base.extend<{ searchableDocument: SearchableDocument }>({
  searchableDocument: async ({ request, page }, use) => {
    const unique = randomUUID();
    const registration = await request.post("/api/v1/auth/register", {
      data: {
        displayName: "Search Smoke",
        email: `search-smoke-${unique}@example.com`,
        password: "Search-Smoke-2026!",
      },
    });
    await expect(registration).toBeOK();
    const tokens = await registration.json();
    const headers = { Authorization: `Bearer ${tokens.accessToken}` };

    const keyword = `otterscope${unique.slice(0, 8)}`;
    const title = `Smoke ${keyword} Brief`;
    const created = await request.post("/api/v1/documents", {
      headers,
      data: { title, content: `Search smoke document ${keyword}.` },
    });
    await expect(created).toBeOK();
    const { id } = (await created.json()) as { id: string };

    await expect
      .poll(
        async () => {
          const response = await request.get(
            `/api/v1/search?q=${encodeURIComponent(keyword)}&type=document`,
            { headers },
          );
          await expect(response).toBeOK();
          const body = (await response.json()) as { results?: { id: string }[] };
          return (body.results ?? []).map((result) => String(result.id));
        },
        { timeout: 60_000, message: `Wait for "${title}" to be indexed` },
      )
      .toContain(id);

    await page.addInitScript(({ accessToken, refreshToken }) => {
      localStorage.setItem("otter_access_token", accessToken);
      localStorage.setItem("otter_refresh_token", refreshToken);
    }, tokens);

    await use({ id, title, keyword });
  },
});

export { expect };
