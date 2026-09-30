import { describe, it, expect } from "vitest";
import {
  getPreviewKind,
  getFileExtension,
  getDelimiter,
  parseDelimited,
  looksLikeText,
} from "./file-preview";

describe("getPreviewKind", () => {
  it("classifies images by MIME and by extension", () => {
    expect(getPreviewKind("image/png", "logo.png")).toBe("image");
    expect(getPreviewKind("application/octet-stream", "photo.JPG")).toBe("image");
    expect(getPreviewKind("image/svg+xml", "icon.svg")).toBe("image");
  });

  it("classifies video and audio", () => {
    expect(getPreviewKind("video/mp4", "clip.mp4")).toBe("video");
    expect(getPreviewKind("application/octet-stream", "clip.mov")).toBe("video");
    expect(getPreviewKind("audio/mpeg", "song.mp3")).toBe("audio");
    expect(getPreviewKind("", "voice.wav")).toBe("audio");
  });

  it("classifies PDFs", () => {
    expect(getPreviewKind("application/pdf", "doc.pdf")).toBe("pdf");
    expect(getPreviewKind("application/octet-stream", "report.pdf")).toBe("pdf");
  });

  it("classifies CSV/TSV separately from plain text", () => {
    expect(getPreviewKind("text/csv", "data.csv")).toBe("csv");
    expect(getPreviewKind("text/plain", "data.csv")).toBe("csv");
    expect(getPreviewKind("application/octet-stream", "data.tsv")).toBe("csv");
  });

  it("classifies text and code files", () => {
    expect(getPreviewKind("text/plain", "notes.txt")).toBe("text");
    expect(getPreviewKind("text/plain; charset=utf-8", "notes.txt")).toBe("text");
    expect(getPreviewKind("application/json", "package.json")).toBe("text");
    expect(getPreviewKind("application/octet-stream", "main.ts")).toBe("text");
    expect(getPreviewKind("", "server.py")).toBe("text");
    expect(getPreviewKind(undefined, "README.md")).toBe("text");
  });

  it("classifies office documents", () => {
    expect(
      getPreviewKind("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "a.docx")
    ).toBe("office");
    expect(getPreviewKind("application/msword", "legacy.doc")).toBe("office");
    expect(getPreviewKind("application/octet-stream", "sheet.xlsx")).toBe("office");
    expect(getPreviewKind("application/octet-stream", "deck.pptx")).toBe("office");
  });

  it("classifies archives", () => {
    expect(getPreviewKind("application/zip", "archive.zip")).toBe("archive");
    expect(getPreviewKind("application/gzip", "backup.tar.gz")).toBe("archive");
    expect(getPreviewKind("application/octet-stream", "bundle.7z")).toBe("archive");
  });

  it("falls back to unknown for unsupported types", () => {
    expect(getPreviewKind("application/octet-stream", "binary.bin")).toBe("unknown");
    expect(getPreviewKind("application/x-msdownload", "setup.exe")).toBe("unknown");
    expect(getPreviewKind("", "")).toBe("unknown");
  });
});

describe("getFileExtension", () => {
  it("extracts a lowercase extension", () => {
    expect(getFileExtension("Report.PDF")).toBe("pdf");
    expect(getFileExtension("a.b.c.tar.gz")).toBe("gz");
    expect(getFileExtension("photo.png?X-Amz-Signature=abc")).toBe("png");
  });

  it("returns empty for dotfiles and extensionless names", () => {
    expect(getFileExtension(".gitignore")).toBe("");
    expect(getFileExtension("README")).toBe("");
    expect(getFileExtension("trailing.")).toBe("");
  });
});

describe("getDelimiter", () => {
  it("uses tabs for TSV and commas otherwise", () => {
    expect(getDelimiter("data.tsv")).toBe("\t");
    expect(getDelimiter("data.txt", "text/tab-separated-values")).toBe("\t");
    expect(getDelimiter("data.csv")).toBe(",");
  });
});

describe("parseDelimited", () => {
  it("parses simple CSV rows and drops trailing blank lines", () => {
    expect(parseDelimited("a,b,c\n1,2,3\n")).toEqual([
      ["a", "b", "c"],
      ["1", "2", "3"],
    ]);
  });

  it("honors quoted fields containing commas, quotes and newlines", () => {
    expect(parseDelimited('name,note\r\n"Doe, Jane","said ""hi""\nbye"')).toEqual([
      ["name", "note"],
      ["Doe, Jane", 'said "hi"\nbye'],
    ]);
  });

  it("supports tab-delimited input", () => {
    expect(parseDelimited("a\tb\n1\t2", "\t")).toEqual([
      ["a", "b"],
      ["1", "2"],
    ]);
  });
});

describe("looksLikeText", () => {
  const bytes = (s: string) => new TextEncoder().encode(s);

  it("accepts UTF-8 text with ordinary whitespace", () => {
    expect(looksLikeText(bytes("hello\n\tworld — ünïcode\r\n"))).toBe(true);
    expect(looksLikeText(new Uint8Array())).toBe(true);
  });

  it("rejects binary content", () => {
    expect(looksLikeText(new Uint8Array([0x89, 0x50, 0x4e, 0x47, 0x00, 0x1a]))).toBe(false);
    expect(looksLikeText(new Uint8Array([0xff, 0xfe, 0xfd, 0xfc]))).toBe(false);
  });
});
