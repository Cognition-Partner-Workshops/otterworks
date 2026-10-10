import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import { useSearchParams } from "react-router-dom";
import { fetchPreviewText } from "./fetch-preview-text";
import { LineNumberedText } from "./line-numbered-text";
import type { PreviewRendererProps } from "./preview-types";
import { PreviewLoading } from "./preview-loading";
import { usePreviewRetry } from "./use-preview-retry";

export function MarkdownPreview({ url, retryWithFreshUrl, onError }: PreviewRendererProps) {
  const { url: previewUrl, retry, retryVersion } = usePreviewRetry(url, retryWithFreshUrl, onError);
  const [searchParams, setSearchParams] = useSearchParams();
  const [text, setText] = useState("");
  const [truncated, setTruncated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const isSource = searchParams.get("view") === "source";

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    fetchPreviewText(previewUrl, controller.signal)
      .then((result) => {
        if (controller.signal.aborted) return;
        setText(result.text);
        setTruncated(result.truncated);
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
  const updateView = (source: boolean) => {
    const next = new URLSearchParams(searchParams);
    if (source) next.set("view", "source");
    else next.delete("view");
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="w-full min-w-0">
      <div className="mb-3 flex items-center gap-2">
        <button type="button" onClick={() => updateView(false)} aria-pressed={!isSource} className="rounded px-3 py-1 text-sm">
          Rendered
        </button>
        <button type="button" onClick={() => updateView(true)} aria-pressed={isSource} className="rounded px-3 py-1 text-sm">
          Source
        </button>
      </div>
      {truncated && <p className="mb-2 text-xs text-amber-700">Showing first 500 KB</p>}
      {isSource ? (
        <LineNumberedText text={text} />
      ) : (
        <article className="max-h-[70vh] min-w-0 overflow-auto rounded border border-gray-200 bg-white p-5 prose prose-sm">
          <ReactMarkdown
            skipHtml
            components={{
              img: ({ alt }) => <span>{alt}</span>,
              a: ({ href, children }) => (
                <a href={href} target="_blank" rel="noopener noreferrer">{children}</a>
              ),
            }}
          >
            {text}
          </ReactMarkdown>
        </article>
      )}
    </div>
  );
}
