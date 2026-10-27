import { randomUUID } from "node:crypto";
import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { seedWorkspace } from "./workspace";

async function register(request: APIRequestContext) {
  const name = `sharing-${randomUUID()}`;
  const response = await request.post("/api/v1/auth/register", {
    data: { displayName: name, email: `${name}@example.com`, password: "Sharing-Test-2026!" },
  });
  await expect(response).toBeOK();
  return response.json();
}

export async function seedSharedFile(request: APIRequestContext, page: Page, fileName: string) {
  const recipient = await register(request);
  const owner = await register(request);
  const headers = { Authorization: `Bearer ${owner.accessToken}` };
  const upload = await request.post("/api/v1/files/upload", {
    headers,
    multipart: {
      owner_id: owner.user.id,
      file: { name: fileName, mimeType: "application/pdf", buffer: Buffer.from("%PDF-1.4\n% Roadmap migration fixture\n%%EOF\n") },
    },
  });
  await expect(upload).toBeOK();
  const { file } = await upload.json();
  const share = await request.post(`/api/v1/files/${file.id}/share`, {
    headers, data: { shared_with: recipient.user.id, shared_by: owner.user.id, permission: "viewer" },
  });
  await expect(share).toBeOK();
  const listing = await request.get("/api/v1/files/shared", { headers: { Authorization: `Bearer ${recipient.accessToken}` } });
  await expect(listing).toBeOK();
  expect((await listing.json()).files.map((item: { id: string }) => item.id)).toEqual([file.id]);
  await page.addInitScript(({ accessToken, refreshToken }) => {
    localStorage.setItem("otter_access_token", accessToken);
    localStorage.setItem("otter_refresh_token", refreshToken);
  }, recipient);
  return { id: file.id as string };
}

export async function seedStarredDocument(request: APIRequestContext, page: Page, title: string) {
  await seedWorkspace(request, page);
  await page.goto("/documents");
  const card = page.getByRole("link", { name: new RegExp(title) });
  // starredApi is browser-local (src/lib/api.ts); there is no star HTTP endpoint.
  await card.getByRole("button", { name: "Star", exact: true }).click();
  await expect(card.getByRole("button", { name: "Unstar", exact: true })).toBeVisible();
}
