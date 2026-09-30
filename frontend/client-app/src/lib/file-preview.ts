// Classifies a stored file into the kind of inline preview the UI can render.
// Pure functions, kept out of the React components so they can be unit-tested.

export type PreviewKind =
  | "image"
  | "video"
  | "audio"
  | "pdf"
  | "text"
  | "csv"
  | "office"
  | "archive"
  | "unknown";

const IMAGE_EXTENSIONS = new Set(["png", "jpg", "jpeg", "gif", "webp", "bmp", "svg", "avif", "ico"]);
const VIDEO_EXTENSIONS = new Set(["mp4", "webm", "ogv", "mov", "m4v"]);
const AUDIO_EXTENSIONS = new Set(["mp3", "wav", "ogg", "oga", "m4a", "flac", "aac"]);
const CSV_EXTENSIONS = new Set(["csv", "tsv"]);
const ARCHIVE_EXTENSIONS = new Set(["zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar"]);
const OFFICE_EXTENSIONS = new Set([
  "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf",
]);

const TEXT_MIME_TYPES = new Set([
  "application/json",
  "application/ld+json",
  "application/xml",
  "application/javascript",
  "application/typescript",
  "application/x-yaml",
  "application/yaml",
  "application/x-sh",
  "application/sql",
  "application/x-httpd-php",
  "application/toml",
]);

const TEXT_EXTENSIONS = new Set([
  "txt", "md", "markdown", "log", "json", "xml", "yaml", "yml", "toml", "ini",
  "cfg", "conf", "env", "csv", "js", "jsx", "ts", "tsx", "mjs", "cjs", "css",
  "scss", "less", "html", "htm", "py", "rb", "go", "rs", "java", "kt", "kts",
  "c", "h", "cpp", "cc", "hpp", "cs", "php", "swift", "scala", "sh", "bash",
  "zsh", "sql", "graphql", "gql", "gradle", "properties", "tf", "hcl", "cob", "cbl", "jcl",
]);

const ARCHIVE_MIME_HINTS = ["zip", "tar", "gzip", "x-7z", "x-rar", "x-bzip", "x-xz", "compressed"];
const OFFICE_MIME_HINTS = [
  "msword", "officedocument", "ms-excel", "ms-powerpoint", "opendocument", "rtf",
];

export function getFileExtension(fileName: string): string {
  const clean = fileName.split(/[?#]/)[0];
  const dot = clean.lastIndexOf(".");
  if (dot <= 0 || dot === clean.length - 1) return "";
  return clean.slice(dot + 1).toLowerCase();
}

// MIME type wins when it is specific; the extension is the fallback for files
// stored as application/octet-stream or with no type at all.
export function getPreviewKind(mimeType: string | undefined, fileName = ""): PreviewKind {
  const mime = (mimeType ?? "").toLowerCase().split(";")[0].trim();
  const ext = getFileExtension(fileName);

  if (mime.startsWith("image/") || IMAGE_EXTENSIONS.has(ext)) return "image";
  if (mime.startsWith("video/") || VIDEO_EXTENSIONS.has(ext)) return "video";
  if (mime.startsWith("audio/") || AUDIO_EXTENSIONS.has(ext)) return "audio";
  if (mime === "application/pdf" || ext === "pdf") return "pdf";
  if (mime === "text/csv" || mime === "text/tab-separated-values" || CSV_EXTENSIONS.has(ext)) return "csv";
  if (OFFICE_EXTENSIONS.has(ext) || OFFICE_MIME_HINTS.some((hint) => mime.includes(hint))) return "office";
  if (ARCHIVE_EXTENSIONS.has(ext) || ARCHIVE_MIME_HINTS.some((hint) => mime.includes(hint))) return "archive";
  if (mime.startsWith("text/") || TEXT_MIME_TYPES.has(mime) || TEXT_EXTENSIONS.has(ext)) return "text";
  return "unknown";
}

export const PREVIEW_KIND_LABELS: Record<PreviewKind, string> = {
  image: "Image",
  video: "Video",
  audio: "Audio",
  pdf: "PDF document",
  text: "Text",
  csv: "Spreadsheet (CSV)",
  office: "Office document",
  archive: "Archive",
  unknown: "File",
};

export function getDelimiter(fileName: string, mimeType?: string): string {
  if (getFileExtension(fileName) === "tsv" || mimeType === "text/tab-separated-values") return "\t";
  return ",";
}

// Minimal RFC 4180 parser: quoted fields, escaped quotes, CRLF/LF line endings.
export function parseDelimited(input: string, delimiter = ","): string[][] {
  const rows: string[][] = [];
  let row: string[] = [];
  let field = "";
  let inQuotes = false;

  for (let i = 0; i < input.length; i++) {
    const char = input[i];
    if (inQuotes) {
      if (char === '"') {
        if (input[i + 1] === '"') {
          field += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        field += char;
      }
      continue;
    }
    if (char === '"') {
      inQuotes = true;
    } else if (char === delimiter) {
      row.push(field);
      field = "";
    } else if (char === "\n" || char === "\r") {
      if (char === "\r" && input[i + 1] === "\n") i++;
      row.push(field);
      rows.push(row);
      row = [];
      field = "";
    } else {
      field += char;
    }
  }
  if (field.length > 0 || row.length > 0) {
    row.push(field);
    rows.push(row);
  }
  return rows.filter((r) => r.length > 1 || r[0].trim() !== "");
}

// Heuristic used after fetching a file we could not classify by type: treat it
// as text when the sample decodes cleanly and contains no control characters.
export function looksLikeText(sample: Uint8Array): boolean {
  if (sample.length === 0) return true;
  let suspicious = 0;
  for (let i = 0; i < sample.length; i++) {
    const byte = sample[i];
    if (byte === 0) return false;
    if (byte < 7 || (byte > 13 && byte < 32)) suspicious++;
  }
  if (suspicious / sample.length > 0.02) return false;
  try {
    new TextDecoder("utf-8", { fatal: true }).decode(sample);
    return true;
  } catch {
    return false;
  }
}
