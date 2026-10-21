import { useState, useEffect } from "react";
import {
  File,
  FileText,
  Film,
  Music,
  Archive,
  AlertCircle,
  Download,
  ExternalLink,
} from "lucide-react";
import {
  getPreviewKind,
  getDelimiter,
  parseDelimited,
  looksLikeText,
  PREVIEW_KIND_LABELS,
  type PreviewKind,
} from "@/lib/file-preview";

const MAX_PREVIEW_SIZE = 500_000; // 500 KB — truncate beyond this
const SNIFF_SIZE = 8_192; // bytes sampled to decide whether an unknown file is text

interface FetchedText {
  text: string;
  truncated: boolean;
}

// Reads at most MAX_PREVIEW_SIZE bytes of the object. S3 honors Range (206);
// servers that ignore it return the whole body (200), so we also cap client-side.
async function fetchPreviewText(url: string, signal: AbortSignal): Promise<FetchedText> {
  const res = await fetch(url, {
    signal,
    headers: { Range: `bytes=0-${MAX_PREVIEW_SIZE - 1}` },
  });
  if (!res.ok && res.status !== 206) throw new Error(`HTTP ${res.status}`);
  const buffer = await res.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  const truncated = res.status === 206 || bytes.length > MAX_PREVIEW_SIZE;
  const text = new TextDecoder().decode(bytes.subarray(0, MAX_PREVIEW_SIZE));
  return { text, truncated };
}

function PreviewSpinner() {
  return (
    <div className="w-full text-center py-8">
      <div className="w-6 h-6 border-2 border-otter-600 border-t-transparent rounded-full animate-spin mx-auto" />
      <p className="text-xs text-gray-400 mt-2">Loading preview…</p>
    </div>
  );
}

function PreviewMessage({
  icon: Icon = AlertCircle,
  message,
}: Readonly<{ icon?: typeof AlertCircle; message: string }>) {
  return (
    <div className="text-center py-8">
      <Icon size={48} className="text-gray-300 mx-auto mb-3" />
      <p className="text-sm text-gray-500">{message}</p>
    </div>
  );
}

function TruncationNotice({ what = "contents" }: Readonly<{ what?: string }>) {
  return (
    <p className="text-xs text-amber-600 mt-2 text-center">
      Showing the first {(MAX_PREVIEW_SIZE / 1000).toFixed(0)} KB. Download the file to see the full {what}.
    </p>
  );
}

interface TextFilePreviewProps {
  presignedUrl?: string;
  fileName: string;
}

export function TextFilePreview({ presignedUrl, fileName }: TextFilePreviewProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [truncated, setTruncated] = useState(false);
  // Falls back to iframe when fetch() is blocked (e.g. CORS on cross-origin S3 URLs)
  const [useIframeFallback, setUseIframeFallback] = useState(false);

  useEffect(() => {
    if (!presignedUrl) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setContent(null);
    setUseIframeFallback(false);

    fetchPreviewText(presignedUrl, controller.signal)
      .then((result) => {
        setContent(result.text);
        setTruncated(result.truncated);
      })
      .catch(() => {
        if (!controller.signal.aborted) setUseIframeFallback(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [presignedUrl]);

  if (loading) return <PreviewSpinner />;

  if (!presignedUrl) return <PreviewMessage message="No download URL available" />;

  if (useIframeFallback) {
    return (
      <div className="w-full">
        <iframe
          src={presignedUrl}
          className="w-full min-h-[500px] bg-white rounded-lg border border-gray-200"
          sandbox="allow-same-origin"
          title={`Preview of ${fileName}`}
        />
      </div>
    );
  }

  if (content === null) return <PreviewMessage message="Could not load preview" />;

  const lines = content.split("\n");
  const gutterWidth = String(lines.length).length;

  return (
    <div className="w-full">
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
          <span className="text-xs font-medium text-gray-500 truncate">
            {fileName}
          </span>
          <span className="text-xs text-gray-400">
            {lines.length} line{lines.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="overflow-auto max-h-[600px]">
          <table className="w-full border-collapse">
            <tbody>
              {lines.map((line, i) => (
                <tr key={i} className="hover:bg-gray-50">
                  <td
                    className="sticky left-0 bg-gray-50 text-right select-none px-3 py-0 text-xs text-gray-400 font-mono border-r border-gray-200"
                    style={{ minWidth: `${gutterWidth + 2}ch` }}
                  >
                    {i + 1}
                  </td>
                  <td className="px-4 py-0 whitespace-pre font-mono text-sm text-gray-800 overflow-x-auto">
                    {line || "\u00A0"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {truncated && <TruncationNotice />}
    </div>
  );
}

interface CsvFilePreviewProps {
  presignedUrl?: string;
  fileName: string;
  mimeType?: string;
}

export function CsvFilePreview({ presignedUrl, fileName, mimeType }: CsvFilePreviewProps) {
  const [rows, setRows] = useState<string[][] | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [truncated, setTruncated] = useState(false);

  useEffect(() => {
    if (!presignedUrl) {
      setLoading(false);
      return;
    }

    const controller = new AbortController();
    setLoading(true);
    setRows(null);
    setFailed(false);

    fetchPreviewText(presignedUrl, controller.signal)
      .then((result) => {
        setRows(parseDelimited(result.text, getDelimiter(fileName, mimeType)));
        setTruncated(result.truncated);
      })
      .catch(() => {
        if (!controller.signal.aborted) setFailed(true);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => controller.abort();
  }, [presignedUrl, fileName, mimeType]);

  if (loading) return <PreviewSpinner />;

  // Plain text view when the delimited parse produced nothing tabular.
  if (failed || !rows || rows.length === 0) {
    return <TextFilePreview presignedUrl={presignedUrl} fileName={fileName} />;
  }

  const [header, ...body] = rows;
  // A truncated fetch usually cuts the last row mid-line; hide the fragment.
  const visibleBody = truncated ? body.slice(0, -1) : body;

  return (
    <div className="w-full">
      <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 border-b border-gray-200">
          <span className="text-xs font-medium text-gray-500 truncate">{fileName}</span>
          <span className="text-xs text-gray-400">
            {visibleBody.length} row{visibleBody.length !== 1 ? "s" : ""} · {header.length} column{header.length !== 1 ? "s" : ""}
          </span>
        </div>
        <div className="overflow-auto max-h-[600px]">
          <table className="w-full border-collapse text-sm">
            <thead className="sticky top-0 bg-gray-50">
              <tr>
                {header.map((cell, i) => (
                  <th
                    key={i}
                    className="text-left font-medium text-gray-600 px-3 py-2 border-b border-gray-200 whitespace-nowrap"
                  >
                    {cell}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleBody.map((row, r) => (
                <tr key={r} className="hover:bg-gray-50">
                  {header.map((_, c) => (
                    <td key={c} className="px-3 py-1.5 border-b border-gray-100 text-gray-700 whitespace-nowrap">
                      {row[c] ?? ""}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {truncated && <TruncationNotice what="table" />}
    </div>
  );
}

interface PdfFilePreviewProps {
  presignedUrl?: string;
}

export function PdfFilePreview({ presignedUrl }: PdfFilePreviewProps) {
  if (!presignedUrl) {
    return (
      <div className="text-center py-8">
        <File size={64} className="text-red-400 mx-auto mb-3" />
        <p className="text-sm text-gray-500">PDF preview not available</p>
      </div>
    );
  }

  return (
    <div className="w-full">
      <iframe
        src={presignedUrl}
        className="w-full rounded-lg border border-gray-200"
        style={{ minHeight: "600px" }}
        title="PDF preview"
      />
      <p className="text-xs text-gray-400 mt-2 text-center">
        If the preview doesn&apos;t load,{" "}
        <a
          href={presignedUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="text-otter-600 hover:underline"
        >
          open in a new tab
        </a>
      </p>
    </div>
  );
}

interface ImageFilePreviewProps {
  presignedUrl?: string;
  fileName: string;
}

export function ImageFilePreview({ presignedUrl, fileName }: ImageFilePreviewProps) {
  const [error, setError] = useState(false);

  useEffect(() => {
    setError(false);
  }, [presignedUrl]);

  if (!presignedUrl || error) {
    return (
      <div className="text-center py-8">
        <File size={64} className="text-gray-300 mx-auto mb-3" />
        <p className="text-sm text-gray-500">Image preview not available</p>
      </div>
    );
  }

  return (
    <img
      src={presignedUrl}
      alt={fileName}
      className="max-w-full max-h-[500px] rounded-lg shadow-sm"
      onError={() => setError(true)}
    />
  );
}

interface VideoFilePreviewProps {
  presignedUrl?: string;
}

export function VideoFilePreview({ presignedUrl }: VideoFilePreviewProps) {
  if (!presignedUrl) return <PreviewMessage icon={Film} message="Video preview not available" />;

  return (
    <video src={presignedUrl} controls className="max-w-full max-h-[500px] rounded-lg bg-black">
      <track kind="captions" />
    </video>
  );
}

interface AudioFilePreviewProps {
  presignedUrl?: string;
  fileName: string;
}

export function AudioFilePreview({ presignedUrl, fileName }: AudioFilePreviewProps) {
  if (!presignedUrl) return <PreviewMessage icon={Music} message="Audio preview not available" />;

  return (
    <div className="w-full max-w-md text-center">
      <div className="w-20 h-20 rounded-2xl bg-otter-50 flex items-center justify-center mx-auto mb-4">
        <Music size={36} className="text-otter-600" />
      </div>
      <p className="text-sm font-medium text-gray-700 truncate mb-3">{fileName}</p>
      <audio src={presignedUrl} controls className="w-full">
        <track kind="captions" />
      </audio>
    </div>
  );
}

interface UnsupportedFilePreviewProps {
  presignedUrl?: string;
  fileName: string;
  mimeType: string;
  kind: PreviewKind;
  onDownload?: () => void;
}

const UNSUPPORTED_ICONS: Partial<Record<PreviewKind, typeof File>> = {
  office: FileText,
  archive: Archive,
};

const UNSUPPORTED_MESSAGES: Partial<Record<PreviewKind, string>> = {
  office: "Inline preview isn't available for this document type yet.",
  archive: "Archives can't be previewed inline.",
};

export function UnsupportedFilePreview({
  presignedUrl,
  fileName,
  mimeType,
  kind,
  onDownload,
}: UnsupportedFilePreviewProps) {
  const Icon = UNSUPPORTED_ICONS[kind] ?? File;
  return (
    <div className="text-center py-6 max-w-sm">
      <div className="w-20 h-20 rounded-2xl bg-gray-100 flex items-center justify-center mx-auto mb-4">
        <Icon size={36} className="text-gray-400" />
      </div>
      <p className="text-sm font-medium text-gray-700 truncate mb-1">{fileName}</p>
      <p className="text-xs text-gray-400 mb-1">
        {PREVIEW_KIND_LABELS[kind]}
        {mimeType ? ` · ${mimeType}` : ""}
      </p>
      <p className="text-xs text-gray-500 mb-4">
        {UNSUPPORTED_MESSAGES[kind] ?? "No inline preview is available for this file type."}
      </p>
      <div className="flex items-center justify-center gap-2">
        {onDownload && (
          <button
            onClick={onDownload}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm text-white bg-otter-600 rounded-lg hover:bg-otter-700 transition"
          >
            <Download size={16} />
            Download
          </button>
        )}
        {presignedUrl && (
          <a
            href={presignedUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-2 px-4 py-2 text-sm text-otter-700 bg-otter-50 rounded-lg hover:bg-otter-100 transition"
          >
            <ExternalLink size={16} />
            Open in new tab
          </a>
        )}
      </div>
    </div>
  );
}

interface SniffedFilePreviewProps {
  presignedUrl?: string;
  fileName: string;
  mimeType: string;
  onDownload?: () => void;
}

// For files we can't classify from metadata: sample the first bytes and show
// them as text if they decode cleanly, otherwise fall back to the generic card.
function SniffedFilePreview({ presignedUrl, fileName, mimeType, onDownload }: SniffedFilePreviewProps) {
  const [isText, setIsText] = useState<boolean | null>(null);

  useEffect(() => {
    if (!presignedUrl) {
      setIsText(false);
      return;
    }
    const controller = new AbortController();
    setIsText(null);
    fetch(presignedUrl, {
      signal: controller.signal,
      headers: { Range: `bytes=0-${SNIFF_SIZE - 1}` },
    })
      .then(async (res) => {
        if (!res.ok && res.status !== 206) throw new Error(`HTTP ${res.status}`);
        const bytes = new Uint8Array(await res.arrayBuffer());
        setIsText(looksLikeText(bytes.subarray(0, SNIFF_SIZE)));
      })
      .catch(() => {
        if (!controller.signal.aborted) setIsText(false);
      });
    return () => controller.abort();
  }, [presignedUrl]);

  if (isText === null) return <PreviewSpinner />;
  if (isText) return <TextFilePreview presignedUrl={presignedUrl} fileName={fileName} />;
  return (
    <UnsupportedFilePreview
      presignedUrl={presignedUrl}
      fileName={fileName}
      mimeType={mimeType}
      kind="unknown"
      onDownload={onDownload}
    />
  );
}

export interface FilePreviewProps {
  fileName: string;
  mimeType: string;
  presignedUrl?: string;
  isUrlLoading?: boolean;
  onDownload?: () => void;
}

// Picks the right inline renderer for a file and degrades gracefully for
// anything the browser can't display. Shared by the file-detail page and the
// quick-preview modal so both behave identically.
export function FilePreview({ fileName, mimeType, presignedUrl, isUrlLoading, onDownload }: FilePreviewProps) {
  const kind = getPreviewKind(mimeType, fileName);

  if (isUrlLoading) return <PreviewSpinner />;

  switch (kind) {
    case "image":
      return <ImageFilePreview presignedUrl={presignedUrl} fileName={fileName} />;
    case "video":
      return <VideoFilePreview presignedUrl={presignedUrl} />;
    case "audio":
      return <AudioFilePreview presignedUrl={presignedUrl} fileName={fileName} />;
    case "pdf":
      return <PdfFilePreview presignedUrl={presignedUrl} />;
    case "csv":
      return <CsvFilePreview presignedUrl={presignedUrl} fileName={fileName} mimeType={mimeType} />;
    case "text":
      return <TextFilePreview presignedUrl={presignedUrl} fileName={fileName} />;
    case "office":
    case "archive":
      return (
        <UnsupportedFilePreview
          presignedUrl={presignedUrl}
          fileName={fileName}
          mimeType={mimeType}
          kind={kind}
          onDownload={onDownload}
        />
      );
    default:
      return (
        <SniffedFilePreview
          presignedUrl={presignedUrl}
          fileName={fileName}
          mimeType={mimeType}
          onDownload={onDownload}
        />
      );
  }
}
