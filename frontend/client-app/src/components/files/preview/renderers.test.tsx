import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { MarkdownPreview } from "./markdown-preview";
import { CsvPreview } from "./csv-preview";
import { DocxPreview } from "./docx-preview";
import { TextPreview } from "./text-preview";

const retryWithFreshUrl = vi.fn().mockResolvedValue("http://storage/new");

vi.mock("./docx-conversion", () => ({
  convertDocxToHtml: vi.fn().mockResolvedValue(
    '<h1>Safe</h1><script>alert(1)</script><img src=x onerror="alert(1)">',
  ),
}));

describe("preview renderers", () => {
  it("renders markdown heading and switches between rendered and source (AC-09, BDD-03)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("# Preview heading\n\nSome text")));
    render(<MemoryRouter><MarkdownPreview url="http://storage/file" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Preview heading" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Source" }));
    expect(await screen.findByTestId("line-number-content")).toHaveTextContent("# Preview heading");
    expect(screen.getByRole("button", { name: "Rendered" })).toBeInTheDocument();
  });

  it("skips raw HTML and renders Markdown image alt text without an img (AC-31)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(
      "# Safe\n\n<script>alert(1)</script>\n\n<img src='https://invalid.test/pixel' alt='raw image alt' onerror='alert(1)'>\n\n![diagram](http://x/y.png)",
    )));
    render(<MemoryRouter><MarkdownPreview url="http://storage/file" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    await screen.findByRole("heading", { name: "Safe" });
    expect(document.querySelector("script")).not.toBeInTheDocument();
    expect(document.querySelector("img")).not.toBeInTheDocument();
    expect(screen.getByText("diagram")).toBeInTheDocument();
    expect(screen.queryByText("raw image alt")).not.toBeInTheDocument();
  });

  it("preserves angle brackets in fenced code blocks (AC-31)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("```java\nList<String> x;\n```")));
    render(<MemoryRouter><MarkdownPreview url="http://storage/file" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    expect(await screen.findByText("List<String> x;")).toBeInTheDocument();
  });

  it("parses comma-delimited CSV with the first row as headers and parses TSV (AC-10)", async () => {
    vi.stubGlobal("fetch", vi.fn()
      .mockResolvedValueOnce(new Response("Name,Count\nOtter,2\n"))
      .mockResolvedValueOnce(new Response("Name\tCount\nOtter\t2\n")));
    const { rerender } = render(<MemoryRouter><CsvPreview url="http://storage/file.csv" name="file.csv" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    expect(await screen.findByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "2" })).toBeInTheDocument();
    rerender(<MemoryRouter><CsvPreview url="http://storage/file.tsv" name="file.tsv" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    expect(await screen.findByRole("columnheader", { name: "Count" })).toBeInTheDocument();
  });

  it("renders at most 1,000 CSV data rows and announces the total (AC-10, BDD-10)", async () => {
    const csv = ["Name", ...Array.from({ length: 1_500 }, (_, index) => `row-${index + 1}`)].join("\n");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(csv)));
    render(<MemoryRouter><CsvPreview url="http://storage/file.csv" name="file.csv" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);

    expect(await screen.findByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getAllByRole("cell")).toHaveLength(1_000);
    expect(screen.getByText("Showing first 1,000 of 1,500 rows")).toBeInTheDocument();
    expect(screen.queryByRole("cell", { name: "row-1500" })).not.toBeInTheDocument();
  });

  it("shows both byte and row notices when a large CSV exceeds both limits (AC-10, AC-35)", async () => {
    const csv = ["Name,Value", ...Array.from(
      { length: 1_500 },
      (_, index) => `row-${index + 1},${"x".repeat(400)}`,
    )].join("\n");
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(csv, {
      status: 206,
      headers: { "Content-Range": `bytes 0-499999/${csv.length}` },
    })));
    render(<MemoryRouter><CsvPreview url="http://storage/file.csv" name="file.csv" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);

    expect(await screen.findByRole("columnheader", { name: "Name" })).toBeInTheDocument();
    expect(screen.getByText("Showing first 500 KB")).toBeInTheDocument();
    expect(screen.getByText(/^Showing first 1,000 of [\d,]+ rows$/)).toBeInTheDocument();
  });

  it("drops the partial last CSV row when the byte cap truncates input (AC-10, AC-35)", async () => {
    const body = `Header\n${"complete\n".repeat(20)}partial`;
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, {
      status: 206,
      headers: { "Content-Range": "bytes 0-499999/600000" },
    })));
    render(<MemoryRouter><CsvPreview url="http://storage/file.csv" name="file.csv" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    await screen.findByRole("columnheader", { name: "Header" });
    expect(screen.queryByRole("cell", { name: "partial" })).not.toBeInTheDocument();
    expect(screen.getByText("Showing first 500 KB")).toBeInTheDocument();
  });

  it("sanitizes DOCX HTML before rendering (AC-14, AC-31)", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(new ArrayBuffer(4))));
    render(<MemoryRouter><DocxPreview url="http://storage/file.docx" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    expect(await screen.findByRole("heading", { name: "Safe" })).toBeInTheDocument();
    await waitFor(() => expect(document.querySelector("script")).not.toBeInTheDocument());
    expect(document.querySelector("[onerror]")).not.toBeInTheDocument();
  });

  it("requests only the initial 500,000 bytes and announces truncated text (AC-07, AC-08, AC-35)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("line one\nline two", {
      status: 206,
      headers: { "Content-Range": "bytes 0-499999/680000" },
    }));
    vi.stubGlobal("fetch", fetchMock);
    render(<MemoryRouter><TextPreview url="http://storage/file.log" retryWithFreshUrl={retryWithFreshUrl} /></MemoryRouter>);
    expect(await screen.findByTestId("line-number-content")).toHaveTextContent("line one");
    expect(screen.getByText("Showing first 500 KB")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith(
      "http://storage/file.log",
      expect.objectContaining({ headers: expect.objectContaining({ Range: "bytes=0-499999" }) }),
    ));
  });
});
