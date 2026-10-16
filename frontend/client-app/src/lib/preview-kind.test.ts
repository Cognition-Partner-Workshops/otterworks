import { describe, expect, it } from "vitest";
import { resolvePreviewKind } from "./preview-kind";

describe("resolvePreviewKind (AC-05, AC-16, AC-17, AC-18)", () => {
  it.each([
    ["image/png", "photo.png", "image"],
    ["image/svg+xml", "diagram.svg", "image"],
    ["application/pdf", "report.pdf", "pdf"],
    ["text/plain", "notes.txt", "text"],
    ["text/csv", "data.csv", "csv"],
    ["text/markdown", "notes.md", "markdown"],
    ["text/x-python", "script.py", "text"],
    ["text/x-log", "events.log", "text"],
    ["text/html", "page.html", "text"],
    ["application/json", "data.json", "text"],
    ["application/octet-stream", "README", "unsupported"],
    ["application/vnd.openxmlformats-officedocument.wordprocessingml.document", "report.docx", "docx"],
    ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "data.xlsx", "xlsx"],
    ["application/vnd.openxmlformats-officedocument.presentationml.presentation", "slides.pptx", "unsupported"],
    ["application/msword", "report.doc", "unsupported"],
    ["application/vnd.ms-excel", "data.xls", "unsupported"],
    ["application/vnd.ms-powerpoint", "slides.ppt", "unsupported"],
    ["application/zip", "archive.zip", "zip"],
    ["application/x-zip-compressed", "archive.zip", "zip"],
    ["audio/wav", "audio.wav", "audio"],
    ["audio/mpeg", "audio.mp3", "audio"],
    ["video/webm", "clip.webm", "video"],
    ["video/mp4", "clip.mp4", "video"],
  ] as const)("maps %s (%s) to %s", (mime, name, expected) => {
    expect(resolvePreviewKind(mime, name)).toBe(expected);
  });

  it.each([
    ["", "README", "unsupported"],
    ["application/octet-stream", "README", "unsupported"],
    ["application/octet-stream", "notes.md", "markdown"],
    ["application/octet-stream", "values.csv", "csv"],
    ["application/octet-stream", "values.tsv", "csv"],
    ["application/octet-stream", "x.docx", "docx"],
    ["application/octet-stream", "x.xlsx", "xlsx"],
    ["application/octet-stream", "x.pptx", "unsupported"],
    ["", "x.py", "text"],
    ["", "x.svg", "image"],
    ["", "x.zip", "zip"],
    ["", "x.wav", "audio"],
    ["", "x.webm", "video"],
    ["application/octet-stream", "file.unknown", "unsupported"],
  ] as const)("uses extension fallback for %s / %s → %s (AC-17)", (mime, name, expected) => {
    expect(resolvePreviewKind(mime, name)).toBe(expected);
  });

  it("does not override a specific unknown MIME with a known extension (AC-17)", () => {
    expect(resolvePreviewKind("application/x-custom", "notes.md")).toBe("unsupported");
  });
});
