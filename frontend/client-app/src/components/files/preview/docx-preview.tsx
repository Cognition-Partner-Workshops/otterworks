import DOMPurify from "dompurify";
import { useEffect, useState } from "react";
import { convertDocxToHtml } from "./docx-conversion";
import { PreviewLoading } from "./preview-loading";
import type { PreviewRendererProps } from "./preview-types";
import { usePreviewRetry } from "./use-preview-retry";

export function DocxPreview({ url, retryWithFreshUrl, onError }: PreviewRendererProps) {
  const { url: previewUrl, retry, retryVersion } = usePreviewRetry(url, retryWithFreshUrl, onError);
  const [html, setHtml] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    fetch(previewUrl, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`DOCX preview failed with status ${response.status}`);
        return response.arrayBuffer();
      })
      .then((buffer) => convertDocxToHtml(buffer))
      .then((converted) => {
        if (!controller.signal.aborted) setHtml(DOMPurify.sanitize(converted));
      })
      .catch(() => {
        if (!controller.signal.aborted) void retry();
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [previewUrl, retryVersion, retry]);

  if (isLoading) return <PreviewLoading />;
  return (
    <article
      className="max-h-[70vh] w-full min-w-0 overflow-auto rounded border border-gray-200 bg-white p-5 prose prose-sm"
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
