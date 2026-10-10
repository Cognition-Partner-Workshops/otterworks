import { lazy, Suspense, useCallback, useState } from "react";
import type { FileItem } from "@/types";
import { usePreviewUrl } from "@/hooks/use-preview-url";
import {
  PREVIEW_AUTOLOAD_LIMIT,
  resolvePreviewKind,
  type PreviewKind,
} from "@/lib/preview-kind";
import { ErrorBoundary } from "@/components/ui/error-boundary";
import { LargeFileGate } from "./large-file-gate";
import { PreviewError } from "./preview-error";
import { PreviewLoading } from "./preview-loading";
import { UnsupportedPreview } from "./unsupported-preview";
import type { PreviewRendererProps } from "./preview-types";

const MarkdownPreview = lazy(() =>
  import("./markdown-preview").then((module) => ({ default: module.MarkdownPreview })),
);
const CsvPreview = lazy(() =>
  import("./csv-preview").then((module) => ({ default: module.CsvPreview })),
);
const ZipPreview = lazy(() =>
  import("./zip-preview").then((module) => ({ default: module.ZipPreview })),
);
const DocxPreview = lazy(() =>
  import("./docx-preview").then((module) => ({ default: module.DocxPreview })),
);
const XlsxPreview = lazy(() =>
  import("./xlsx-preview").then((module) => ({ default: module.XlsxPreview })),
);
const ImagePreview = lazy(() =>
  import("./image-preview").then((module) => ({ default: module.ImagePreview })),
);
const PdfPreview = lazy(() =>
  import("./pdf-preview").then((module) => ({ default: module.PdfPreview })),
);
const TextPreview = lazy(() =>
  import("./text-preview").then((module) => ({ default: module.TextPreview })),
);
const MediaPreview = lazy(() =>
  import("./media-preview").then((module) => ({ default: module.MediaPreview })),
);

const gatedKinds = new Set<PreviewKind>(["image", "pdf", "audio", "video", "docx", "xlsx"]);

export function FilePreview({
  file,
  onDownload,
}: {
  file: FileItem;
  onDownload: () => void;
}) {
  if (file.size === 0) {
    return <p className="text-sm text-gray-500">This file is empty</p>;
  }

  const kind = resolvePreviewKind(file.mimeType, file.name);
  if (kind === "unsupported") {
    return (
      <UnsupportedPreview
        name={file.name}
        size={file.size}
        mimeType={file.mimeType}
        onDownload={onDownload}
      />
    );
  }

  return (
    <PreviewWithUrl
      key={file.id}
      file={file}
      kind={kind}
      onDownload={onDownload}
    />
  );
}

function PreviewWithUrl({
  file,
  kind,
  onDownload,
}: {
  file: FileItem;
  kind: PreviewKind;
  onDownload: () => void;
}) {
  const largeGate = gatedKinds.has(kind) && file.size > PREVIEW_AUTOLOAD_LIMIT;
  const [loadLarge, setLoadLarge] = useState(false);
  const [hasError, setHasError] = useState(false);
  const [rendererKey, setRendererKey] = useState(0);
  const handleRendererError = useCallback(() => setHasError(true), []);
  const shouldLoadUrl = !largeGate || loadLarge;
  const { url, isLoading, notFound, error, refresh } = usePreviewUrl(file.id, shouldLoadUrl);

  const retryPreview = useCallback(async () => {
    try {
      await refresh();
      setHasError(false);
      setRendererKey((key) => key + 1);
    } catch {
      setHasError(true);
    }
  }, [refresh]);

  const loadPreview = async () => {
    try {
      await refresh();
      setHasError(false);
      setLoadLarge(true);
    } catch {
      setHasError(true);
      setLoadLarge(true);
    }
  };

  if (isLoading) return <PreviewLoading />;
  if (notFound) return <p className="text-sm text-gray-500">This file is no longer available</p>;
  if (largeGate && !loadLarge) {
    return <LargeFileGate size={file.size} onLoad={() => void loadPreview()} />;
  }
  if (hasError || error) {
    return <PreviewError onRetry={() => void retryPreview()} onDownload={onDownload} />;
  }
  if (!url) return <PreviewLoading />;

  const rendererProps: PreviewRendererProps = {
    url,
    retryWithFreshUrl: refresh,
    onError: handleRendererError,
  };
  let renderer;
  switch (kind) {
    case "image":
      renderer = <ImagePreview {...rendererProps} fileName={file.name} />;
      break;
    case "pdf":
      renderer = <PdfPreview {...rendererProps} fileName={file.name} />;
      break;
    case "text":
      renderer = <TextPreview {...rendererProps} />;
      break;
    case "markdown":
      renderer = <MarkdownPreview {...rendererProps} />;
      break;
    case "csv":
      renderer = <CsvPreview {...rendererProps} name={file.name} />;
      break;
    case "audio":
    case "video":
      renderer = <MediaPreview {...rendererProps} kind={kind} />;
      break;
    case "zip":
      renderer = <ZipPreview {...rendererProps} />;
      break;
    case "docx":
      renderer = <DocxPreview {...rendererProps} />;
      break;
    case "xlsx":
      renderer = <XlsxPreview {...rendererProps} />;
      break;
    default:
      renderer = null;
  }

  return (
    <ErrorBoundary
      key={rendererKey}
      fallback={<PreviewError onRetry={() => void retryPreview()} onDownload={onDownload} />}
    >
      <Suspense fallback={<PreviewLoading />}>{renderer}</Suspense>
    </ErrorBoundary>
  );
}
