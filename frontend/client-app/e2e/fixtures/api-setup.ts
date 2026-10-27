import { randomUUID } from "node:crypto";
import { test as base, expect, type APIRequestContext } from "@playwright/test";

export interface ApiUser {
  id: string;
  email: string;
  displayName: string;
  password: string;
  accessToken: string;
  refreshToken: string;
}

interface UploadedFile {
  id: string;
  name: string;
}

interface FileInput {
  name: string;
  mimeType: string;
  content: string;
}

interface ApiFixtures {
  api: APIRequestContext;
  createUser: () => Promise<ApiUser>;
  uploadFile: (owner: ApiUser, input: FileInput) => Promise<UploadedFile>;
  shareFile: (owner: ApiUser, fileId: string, recipient: ApiUser, permission: "viewer" | "editor") => Promise<void>;
  signInAs: (user: ApiUser) => Promise<void>;
  sharedFile: { owner: ApiUser; recipient: ApiUser; file: UploadedFile; content: string };
}

const bearer = (user: ApiUser) => ({ Authorization: `Bearer ${user.accessToken}` });

export const test = base.extend<ApiFixtures>({
  api: async ({ playwright }, provide) => {
    const api = await playwright.request.newContext({
      baseURL: process.env.API_GATEWAY_URL || "http://localhost:8080",
    });
    try {
      await provide(api);
    } finally {
      await api.dispose();
    }
  },
  createUser: async ({ api }, provide) => {
    await provide(async () => {
      const unique = randomUUID();
      const password = `Shared-${randomUUID()}!`;
      const email = `sharing-${unique}@example.com`;
      const displayName = `Sharing ${unique}`;
      const response = await api.post("/api/v1/auth/register", {
        data: { email, displayName, password },
      });
      await expect(response).toBeOK();
      const body = await response.json();
      return { id: body.user.id, email, displayName, password,
        accessToken: body.accessToken, refreshToken: body.refreshToken };
    });
  },
  uploadFile: async ({ api }, provide) => {
    await provide(async (owner, input) => {
      const response = await api.post("/api/v1/files/upload", {
        headers: bearer(owner),
        multipart: {
          owner_id: owner.id,
          file: { name: input.name, mimeType: input.mimeType, buffer: Buffer.from(input.content) },
        },
      });
      await expect(response).toBeOK();
      return (await response.json()).file;
    });
  },
  shareFile: async ({ api }, provide) => {
    await provide(async (owner, fileId, recipient, permission) => {
      const response = await api.post(`/api/v1/files/${fileId}/share`, {
        headers: bearer(owner),
        data: { shared_with: recipient.id, shared_by: owner.id, permission },
      });
      await expect(response).toBeOK();
    });
  },
  signInAs: async ({ page }, provide) => {
    await provide(async (user) => {
      await page.addInitScript(({ accessToken, refreshToken }) => {
        localStorage.setItem("otter_access_token", accessToken);
        localStorage.setItem("otter_refresh_token", refreshToken);
      }, user);
    });
  },
  sharedFile: async ({ api, createUser, uploadFile, shareFile, signInAs }, provide) => {
    const owner = await createUser();
    const recipient = await createUser();
    const content = "Q3 vendor contract: recipient read-only fixture.\n";
    const file = await uploadFile(owner, {
      name: "Q3 vendor contract.txt", mimeType: "text/plain", content,
    });
    try {
      await shareFile(owner, file.id, recipient, "viewer");
      const response = await api.get("/api/v1/files/shared", { headers: bearer(recipient) });
      await expect(response).toBeOK();
      const body: { files: UploadedFile[] } = await response.json();
      expect(body.files.map((item) => item.id)).toEqual([file.id]);
      await signInAs(recipient);
      await provide({ owner, recipient, file, content });
    } finally {
      await expect(await api.delete(`/api/v1/files/${file.id}/share/${recipient.id}`, {
        headers: bearer(owner),
      })).toBeOK();
      await expect(await api.post(`/api/v1/files/${file.id}/trash`, {
        headers: bearer(owner),
      })).toBeOK();
      await expect(await api.delete(`/api/v1/files/${file.id}`, {
        headers: bearer(owner),
      })).toBeOK();
    }
  },
});

export { expect };
