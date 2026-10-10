export type PreviewKind =
  | "image"
  | "pdf"
  | "text"
  | "markdown"
  | "csv"
  | "audio"
  | "video"
  | "zip"
  | "docx"
  | "xlsx"
  | "unsupported";

export const PREVIEW_AUTOLOAD_LIMIT = 104_857_600;
export const TEXT_PREVIEW_BYTES = 500_000;
export const MAX_ARCHIVE_ENTRIES = 1000;
export const MAX_TABLE_ROWS = 1000;

const textMimeTypes = new Set([
  "application/json",
  "application/xml",
  "application/javascript",
  "application/typescript",
  "application/x-yaml",
  "application/x-sh",
]);

const extensionKinds: Record<string, PreviewKind> = {
  md: "markdown",
  markdown: "markdown",
  csv: "csv",
  tsv: "csv",
  txt: "text",
  log: "text",
  json: "text",
  xml: "text",
  yaml: "text",
  yml: "text",
  js: "text",
  jsx: "text",
  ts: "text",
  tsx: "text",
  py: "text",
  java: "text",
  go: "text",
  rs: "text",
  rb: "text",
  sh: "text",
  sql: "text",
  html: "text",
  css: "text",
  png: "image",
  jpg: "image",
  jpeg: "image",
  gif: "image",
  webp: "image",
  bmp: "image",
  avif: "image",
  svg: "image",
  pdf: "pdf",
  mp3: "audio",
  wav: "audio",
  ogg: "audio",
  m4a: "audio",
  flac: "audio",
  mp4: "video",
  webm: "video",
  mov: "video",
  zip: "zip",
  docx: "docx",
  xlsx: "xlsx",
};

const docxMimeTypes = new Set([
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
]);
const xlsxMimeTypes = new Set([
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
]);

export function resolvePreviewKind(mimeType: string, name: string): PreviewKind {
  const mime = mimeType.trim().toLowerCase();

  if (mime === "text/markdown") return "markdown";
  if (mime === "text/csv" || mime === "text/tab-separated-values") return "csv";
  if (mime.startsWith("image/")) return "image";
  if (mime === "application/pdf") return "pdf";
  if (mime.startsWith("audio/")) return "audio";
  if (mime.startsWith("video/")) return "video";
  if (mime === "application/zip" || mime === "application/x-zip-compressed") return "zip";
  if (docxMimeTypes.has(mime)) return "docx";
  if (xlsxMimeTypes.has(mime)) return "xlsx";
  if (
    mime === "application/vnd.openxmlformats-officedocument.presentationml.presentation" ||
    mime === "application/msword" ||
    mime === "application/vnd.ms-excel" ||
    mime === "application/vnd.ms-powerpoint"
  ) {
    return "unsupported";
  }
  if (mime.startsWith("text/") || textMimeTypes.has(mime)) return "text";

  if (!mime || mime === "application/octet-stream") {
    const extension = name.toLowerCase().match(/\.([^.]+)$/)?.[1];
    return extension ? extensionKinds[extension] ?? "unsupported" : "unsupported";
  }

  return "unsupported";
}
