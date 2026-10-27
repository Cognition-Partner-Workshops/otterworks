import { expect, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { seedWorkspace } from "./workspace";

type SearchResult = { id: string };

export async function waitForIndexedItem(
  request: APIRequestContext,
  headers: Record<string, string>,
  query: string,
  id: string,
  opts: { type?: "document" | "file"; timeout?: number } = {},
): Promise<string[]> {
  const getResultIds = async () => {
    const type = opts.type ? `&type=${opts.type}` : "";
    const response = await request.get(`/api/v1/search?q=${encodeURIComponent(query)}${type}`, { headers });
    await expect(response).toBeOK();
    const body = await response.json();
    return (body.results as SearchResult[]).map((result) => result.id);
  };
  await expect
    .poll(getResultIds, {
      timeout: opts.timeout ?? 60_000,
      message: `Wait for "${query}" to be indexed`,
    })
    .toContain(id);
  return getResultIds();
}

export function searchInput(page: Page): Locator {
  // The page search input has no label or aria-label (accessible name only from its placeholder).
  return page.getByRole("main").getByRole("textbox");
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
    await waitForIndexedItem(request, workspace.headers, document.title, document.id, { type: "document" });
  }
  await waitForIndexedItem(request, workspace.headers, file.name, file.id, { type: "file" });

  return { ...workspace, files: [file] };
}
