import { RefreshCw } from "lucide-react";

export function PreviewError({
  onRetry,
  onDownload,
}: {
  onRetry: () => void;
  onDownload: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center" role="alert">
      <p className="text-sm text-gray-600">Could not load preview</p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onRetry}
          className="inline-flex items-center gap-2 rounded-lg border border-gray-300 bg-white px-3 py-2 text-sm text-gray-700 hover:bg-gray-50"
        >
          <RefreshCw size={14} />
          Retry
        </button>
        <button
          type="button"
          onClick={onDownload}
          className="rounded-lg bg-otter-600 px-3 py-2 text-sm text-white hover:bg-otter-700"
        >
          Download
        </button>
      </div>
    </div>
  );
}
