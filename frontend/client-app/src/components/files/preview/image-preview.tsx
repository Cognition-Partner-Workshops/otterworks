import { usePreviewRetry } from "./use-preview-retry";
import type { PreviewRendererProps } from "./preview-types";

export function ImagePreview({
  url,
  fileName,
  retryWithFreshUrl,
  onError,
}: PreviewRendererProps & { fileName: string }) {
  const preview = usePreviewRetry(url, retryWithFreshUrl, onError);

  return (
    <img
      key={preview.retryVersion}
      src={preview.url}
      alt={fileName}
      className="max-h-[70vh] max-w-full rounded-lg object-contain"
      onError={() => void preview.retry()}
    />
  );
}
