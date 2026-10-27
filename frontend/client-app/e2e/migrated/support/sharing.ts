import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { registerUser } from "./account";
import { seedWorkspace } from "./workspace";

export async function seedSharedFile(request: APIRequestContext, page: Page, fileName: string) {
  const recipient = await registerUser(request, undefined, {
    displayName: "Sharing Recipient",
    emailPrefix: "sharing-recipient",
    password: "Sharing-Test-2026!",
  });
  const owner = await registerUser(request, undefined, {
    displayName: "Sharing Owner",
    emailPrefix: "sharing-owner",
    password: "Sharing-Test-2026!",
  });
  const upload = await request.post("/api/v1/files/upload", {
    headers: owner.headers,
    multipart: {
      owner_id: owner.id,
      file: { name: fileName, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n% Roadmap migration fixture\n%%EOF\n") },
    },
  });
  await expect(upload).toBeOK();
  const { file } = await upload.json();
  const share = await request.post(`/api/v1/files/${file.id}/share`, {
    headers: owner.headers,
    data: { shared_with: recipient.id, shared_by: owner.id, permission: "viewer" },
  });
  await expect(share).toBeOK();
  const listing = await request.get("/api/v1/files/shared", { headers: recipient.headers });
  await expect(listing).toBeOK();
  expect((await listing.json()).files.map((item: { id: string }) => item.id)).toEqual([file.id]);
  await page.addInitScript(({ accessToken, refreshToken }) => {
    localStorage.setItem("otter_access_token", accessToken);
    localStorage.setItem("otter_refresh_token", refreshToken);
  }, { accessToken: recipient.accessToken, refreshToken: recipient.refreshToken });
  return { id: file.id as string };
}

export async function seedStarredDocument(request: APIRequestContext, page: Page, title: string) {
  const workspace = await seedWorkspace(request, page, "Starred");
  const document = workspace.documents.find((seeded) => seeded.title === title);
  if (!document) throw new Error(`Workspace seed did not include "${title}"`);
  return {
    userId: workspace.userId,
    documentId: document.id,
    headers: workspace.headers,
    documents: workspace.documents,
  };
}

export async function starDocumentViaUi(page: Page, title: string): Promise<void> {
  await page.goto("/documents");
  const card = page.getByRole("link", { name: new RegExp(title) });
  await card.getByRole("button", { name: "Star", exact: true }).click();
  await expect(card.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
}

export async function expectStarredItem(page: Page, userId: string, documentId: string): Promise<void> {
  await expect
    .poll(() =>
      page.evaluate(({ userId, documentId }) => {
        const stored = localStorage.getItem("otter_starred_items");
        const items = stored ? (JSON.parse(stored) as Record<string, { itemId: string; itemType: string }>) : {};
        return items[`${userId}:${documentId}`] ?? null;
      }, { userId, documentId }),
    )
    .toMatchObject({ itemId: documentId, itemType: "document" });
}
