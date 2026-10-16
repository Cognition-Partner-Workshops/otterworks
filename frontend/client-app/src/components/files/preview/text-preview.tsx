import { useEffect, useState } from "react";
import { fetchPreviewText, type PreviewText } from "./fetch-preview-text";
import { LineNumberedText } from "./line-numbered-text";
import type { PreviewRendererProps } from "./preview-types";
import { PreviewLoading } from "./preview-loading";
import { usePreviewRetry } from "./use-preview-retry";

export function TextPreview({
  url,
  retryWithFreshUrl,
  onError,
}: PreviewRendererProps) {
  const { url: previewUrl, retry, retryVersion } = usePreviewRetry(url, retryWithFreshUrl, onError);
  const [content, setContent] = useState<PreviewText>();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setContent(undefined);
    fetchPreviewText(previewUrl, controller.signal)
      .then((result) => {
        if (!controller.signal.aborted) setContent(result);
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
  if (!content) return null;

  return (
    <div className="w-full min-w-0">
      {content.truncated && <p className="mb-2 text-xs text-amber-700">Showing first 500 KB</p>}
      <LineNumberedText text={content.text} />
    </div>
  );
}
