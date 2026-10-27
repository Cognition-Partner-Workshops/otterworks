import { randomUUID } from "node:crypto";
import { expect, type APIRequestContext } from "@playwright/test";
import type { Account } from "./accounts";

export type SeededDocument = { id: string; title: string; text: string };
export type SeededFile = { id: string; name: string; text: string };

export async function createDocument(
  request: APIRequestContext,
  owner: Account,
  { title, text }: { title?: string; text?: string } = {},
): Promise<SeededDocument> {
  const uuid = randomUUID();
  const documentTitle = title ?? `Smoke document ${uuid}`;
  const documentText = text ?? `Smoke body ${uuid}`;
  const response = await request.post("/api/v1/documents", {
    headers: owner.headers,
    data: { title: documentTitle, content: `<p>${documentText}</p>` },
  });
  await expect(response).toBeOK();
  const body = await response.json();
  return { id: body.id, title: documentTitle, text: documentText };
}

export async function deleteDocument(
  request: APIRequestContext,
  owner: Account,
  id: string,
): Promise<void> {
  const response = await request.delete(`/api/v1/documents/${id}`, {
    headers: owner.headers,
  });
  await expect(response).toBeOK();
}

export async function uploadTextFile(
  request: APIRequestContext,
  owner: Account,
  { name, text }: { name?: string; text?: string } = {},
): Promise<SeededFile> {
  const uuid = randomUUID();
  const fileName = name ?? `smoke-file-${uuid}.txt`;
  const fileText = text ?? `Smoke file ${uuid}`;
  const response = await request.post("/api/v1/files/upload", {
    headers: owner.headers,
    multipart: {
      file: {
        name: fileName,
        mimeType: "text/plain",
        buffer: Buffer.from(fileText),
      },
      owner_id: owner.id,
    },
  });
  await expect(response).toBeOK();
  const body = await response.json();
  return { id: body.file.id, name: fileName, text: fileText };
}

export async function trashFile(
  request: APIRequestContext,
  owner: Account,
  fileId: string,
): Promise<void> {
  const trashed = await request.post(`/api/v1/files/${fileId}/trash`, {
    headers: owner.headers,
  });
  await expect(trashed).toBeOK();
  const response = await request.get("/api/v1/files/trash", {
    headers: owner.headers,
    params: { owner_id: owner.id },
  });
  await expect(response).toBeOK();
  expect((await response.json()).files).toEqual([
    expect.objectContaining({ id: fileId }),
  ]);
}

export async function shareFile(
  request: APIRequestContext,
  owner: Account,
  fileId: string,
  recipient: Account,
): Promise<void> {
  const response = await request.post(`/api/v1/files/${fileId}/share`, {
    headers: owner.headers,
    data: {
      shared_with: recipient.id,
      shared_by: owner.id,
      permission: "viewer",
    },
  });
  expect(response.status(), await response.text()).toBe(201);
}

export async function waitUntilIndexed(
  request: APIRequestContext,
  owner: Account,
  keyword: string,
  id: string,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `/api/v1/search?q=${encodeURIComponent(keyword)}&type=document`,
          { headers: owner.headers },
        );
        await expect(response).toBeOK();
        const body = await response.json();
        return (body.results ?? []).map((result: { id: string }) =>
          String(result.id),
        );
      },
      {
        timeout: 20_000,
        message: `Wait for "${keyword}" to be indexed`,
      },
    )
    .toContain(id);
}

export async function waitForNotification(
  request: APIRequestContext,
  account: Account,
  resourceId: string,
): Promise<void> {
  await expect
    .poll(
      async () => {
        const response = await request.get("/api/v1/notifications", {
          headers: account.headers,
        });
        const body = await response.json();
        return (body.data ?? []).some(
          (notification: { resourceId?: string }) =>
            notification.resourceId === resourceId,
        );
      },
      {
        timeout: 20_000,
        message: `Wait for the notification about ${resourceId}`,
      },
    )
    .toBe(true);
}

export function starredItemsScript({
  userId,
  documentId,
}: {
  userId: string;
  documentId: string;
}) {
  if (localStorage.getItem("otter_starred_items") === null) {
    localStorage.setItem(
      "otter_starred_items",
      JSON.stringify({
        [`${userId}:${documentId}`]: {
          itemId: documentId,
          itemType: "document",
          starredAt: new Date().toISOString(),
        },
      }),
    );
  }
}
