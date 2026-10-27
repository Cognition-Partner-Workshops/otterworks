import { expect, type APIRequestContext, type Page } from "@playwright/test";
import { seedWorkspace } from "./workspace";

type SearchResult = { id: string };

async function waitForIndexedItem(
  request: APIRequestContext,
  headers: Record<string, string>,
  query: string,
  type: "document" | "file",
  id: string,
) {
  await expect
    .poll(
      async () => {
        const response = await request.get(
          `/api/v1/search?q=${encodeURIComponent(query)}&type=${type}`,
          { headers },
        );
        await expect(response).toBeOK();
        const body = await response.json();
        return (body.results as SearchResult[]).map((result) => result.id);
      },
      {
        timeout: 60_000,
        message: `Wait for ${type} "${query}" to be indexed`,
      },
    )
    .toContain(id);
}

export async function seedSearchWorkspace(request: APIRequestContext, page: Page) {
  const workspace = await seedWorkspace(request, page, "Search");
  const name = "Release Notes.txt";
  const content = "Release notes for the upcoming release.";
  const upload = await request.post("/api/v1/files/upload", {
    headers: workspace.headers,
    multipart: {
      file: {
        name,
        mimeType: "text/plain",
        buffer: Buffer.from(content),
      },
      owner_id: workspace.userId,
    },
  });
  await expect(upload).toBeOK();
  const body = await upload.json();
  const file = { id: body.file.id as string, name: body.file.name as string };

  for (const document of workspace.documents) {
    await waitForIndexedItem(request, workspace.headers, document.title, "document", document.id);
  }
  await waitForIndexedItem(request, workspace.headers, file.name, "file", file.id);

  return { ...workspace, files: [file] };
}
