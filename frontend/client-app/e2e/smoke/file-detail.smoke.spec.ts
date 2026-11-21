import { test, expect } from "../fixtures/fixtures";

test(
  "file detail shows the uploaded file and its preview",
  {
    tag: ["@smoke", "@page-file-detail"],
    annotation: { type: "route", description: "/files/:id" },
  },
  async ({ page, textFile }) => {
    await page.goto(`/files/${textFile.id}`);

    const main = page.getByRole("main");
    await expect(main.getByRole("heading", { level: 1, name: textFile.name })).toBeVisible();
    // The local S3 bucket has no CORS, so the preview uses the app's iframe fallback; the iframe has no role, only a title.
    const preview = main.getByTitle(`Preview of ${textFile.name}`).contentFrame();
    // The raw text/plain document has no roles; its text is the only handle.
    await expect(preview.getByText(textFile.text)).toBeVisible();
  },
);
