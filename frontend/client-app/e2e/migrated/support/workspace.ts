import { randomUUID } from "node:crypto";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

const documents = [
  ["Quarterly Planning", "Review objectives, delivery dates, and ownership for the next quarter."],
  ["Release Checklist", "Confirm approvals, smoke tests, and release notes before publishing."],
  ["Support Handoff", "Open items and escalation contacts for the support rotation."],
  ["Workspace Guide", "A short guide to folders, search, and shared documents."],
] as const;

export async function seedWorkspace(request: APIRequestContext, page: Page, label = "Documents") {
  const registration = await request.post("/api/v1/auth/register", {
    data: { displayName: `${label} Migration`, email: `${label.toLowerCase()}-${randomUUID()}@example.com`, password: "Documents-Test-2026!" },
  });
  await expect(registration).toBeOK();
  const tokens = await registration.json();
  const headers = { Authorization: `Bearer ${tokens.accessToken}` };
  const userId = tokens.user.id as string;
  const seeded: { id: string; title: string }[] = [];
  for (const [title, content] of documents) {
    const response = await request.post("/api/v1/documents", { headers, data: { title, content } });
    await expect(response).toBeOK();
    seeded.push(await response.json());
  }
  const listing = await request.get("/api/v1/documents", { headers });
  await expect(listing).toBeOK();
  const body = await listing.json();
  if (body.total !== documents.length) throw new Error(`Workspace seed: expected total 4, received ${body.total}`);
  await page.addInitScript(({ accessToken, refreshToken }) => {
    localStorage.setItem("otter_access_token", accessToken);
    localStorage.setItem("otter_refresh_token", refreshToken);
  }, tokens);
  return { documents: seeded, total: body.total as number, headers, userId };
}
