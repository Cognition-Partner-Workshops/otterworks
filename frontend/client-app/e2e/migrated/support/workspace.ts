import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { registerUser } from "./account";

const documents = [
  ["Quarterly Planning", "Review objectives, delivery dates, and ownership for the next quarter."],
  ["Release Checklist", "Confirm approvals, smoke tests, and release notes before publishing."],
  ["Support Handoff", "Open items and escalation contacts for the support rotation."],
  ["Workspace Guide", "A short guide to folders, search, and shared documents."],
] as const;

export async function createDocument(
  request: APIRequestContext,
  headers: { Authorization: string },
  doc: { title: string; content: string },
): Promise<{ id: string; title: string }> {
  const response = await request.post("/api/v1/documents", { headers, data: doc });
  await expect(response).toBeOK();
  const document = (await response.json()) as { id: string; title: string };
  expect(document.title).toBe(doc.title);
  return document;
}

export async function deleteDocument(
  request: APIRequestContext,
  headers: { Authorization: string },
  id: string,
): Promise<void> {
  const response = await request.delete(`/api/v1/documents/${id}`, { headers });
  await expect(response).toBeOK();
}

export async function seedWorkspace(request: APIRequestContext, page: Page, label = "Documents") {
  const account = await registerUser(request, page, {
    displayName: `${label} Migration`,
    emailPrefix: label.toLowerCase(),
  });
  const seeded: { id: string; title: string }[] = [];
  for (const [title, content] of documents) {
    seeded.push(await createDocument(request, account.headers, { title, content }));
  }
  const listing = await request.get("/api/v1/documents", { headers: account.headers });
  await expect(listing).toBeOK();
  const body = await listing.json();
  if (body.total !== documents.length) throw new Error(`Workspace seed: expected total 4, received ${body.total}`);
  return { documents: seeded, total: body.total as number, headers: account.headers, userId: account.id };
}
