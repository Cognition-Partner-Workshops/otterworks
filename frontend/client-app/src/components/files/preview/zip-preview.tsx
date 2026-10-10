import { useEffect, useState } from "react";
import { configure, HttpReader, ZipReader } from "@zip.js/zip.js";
import { MAX_ARCHIVE_ENTRIES } from "@/lib/preview-kind";
import { PreviewLoading } from "./preview-loading";
import type { PreviewRendererProps } from "./preview-types";
import { usePreviewRetry } from "./use-preview-retry";

interface ArchiveEntry {
  filename: string;
  uncompressedSize: number;
  directory: boolean;
}

export function ZipPreview({ url, retryWithFreshUrl, onError }: PreviewRendererProps) {
  const { url: previewUrl, retry, retryVersion } = usePreviewRetry(url, retryWithFreshUrl, onError);
  const [entries, setEntries] = useState<ArchiveEntry[]>([]);
  const [totalEntries, setTotalEntries] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    setEntries([]);
    configure({ useWebWorkers: false });
    const reader = new ZipReader(new HttpReader(previewUrl, {
      useRangeHeader: true,
      forceRangeRequests: true,
      preventHeadRequest: true,
      combineSizeEocd: true,
      fetch: (input, init = {}) => fetch(input, { ...init, signal: controller.signal }),
    }));

    reader.getEntries()
      .then((archiveEntries) => {
        if (controller.signal.aborted) return;
        setTotalEntries(archiveEntries.length);
        setEntries(archiveEntries.slice(0, MAX_ARCHIVE_ENTRIES).map((entry) => ({
          filename: entry.filename,
          uncompressedSize: entry.uncompressedSize,
          directory: entry.directory,
        })));
      })
      .catch(() => {
        if (!controller.signal.aborted) void retry();
      })
      .finally(() => {
        void reader.close().catch(() => {});
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [previewUrl, retryVersion, retry]);

  if (isLoading) return <PreviewLoading />;
  return (
    <div className="w-full max-h-[70vh] overflow-auto">
      {totalEntries > MAX_ARCHIVE_ENTRIES && (
        <p className="mb-2 text-xs text-amber-700">Showing 1,000 of {totalEntries}</p>
      )}
      <ul className="divide-y divide-gray-100 rounded border border-gray-200 bg-white">
        {entries.map((entry) => (
          <li key={entry.filename} className="flex items-center justify-between gap-4 px-3 py-2 text-sm">
            <span className="break-all">{entry.filename}{entry.directory ? "/" : ""}</span>
            {!entry.directory && <span className="shrink-0 text-xs text-gray-500">{formatBytes(entry.uncompressedSize)}</span>}
          </li>
        ))}
      </ul>
    </div>
  );
}

function formatBytes(bytes: number) {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}
