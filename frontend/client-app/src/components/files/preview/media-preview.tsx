import { useRef } from "react";
import { usePreviewRetry } from "./use-preview-retry";
import type { PreviewRendererProps } from "./preview-types";

export function MediaPreview({
  url,
  kind,
  retryWithFreshUrl,
  onError,
}: PreviewRendererProps & { kind: "audio" | "video" }) {
  const preview = usePreviewRetry(url, retryWithFreshUrl, onError);
  const currentTime = useRef(0);
  const restoreTime = useRef(false);
  const onMediaError = (event: React.SyntheticEvent<HTMLMediaElement>) => {
    currentTime.current = event.currentTarget.currentTime;
    restoreTime.current = true;
    void preview.retry();
  };
  const onLoadedMetadata = (event: React.SyntheticEvent<HTMLMediaElement>) => {
    if (restoreTime.current) {
      event.currentTarget.currentTime = currentTime.current;
      restoreTime.current = false;
    }
  };

  return kind === "audio" ? (
    <audio
      key={`${preview.url}-${preview.retryVersion}`}
      src={preview.url}
      controls
      preload="metadata"
      className="w-full"
      onError={onMediaError}
      onLoadedMetadata={onLoadedMetadata}
    />
  ) : (
    <video
      key={`${preview.url}-${preview.retryVersion}`}
      src={preview.url}
      controls
      className="max-h-[70vh] max-w-full"
      onError={onMediaError}
      onLoadedMetadata={onLoadedMetadata}
    />
  );
}
