import Papa from "papaparse";
import { useEffect, useState } from "react";
import { fetchPreviewText } from "./fetch-preview-text";
import type { PreviewRendererProps } from "./preview-types";
import { PreviewLoading } from "./preview-loading";
import { usePreviewRetry } from "./use-preview-retry";

export function CsvPreview({
  url,
  name,
  retryWithFreshUrl,
  onError,
}: PreviewRendererProps & { name: string }) {
  const { url: previewUrl, retry, retryVersion } = usePreviewRetry(url, retryWithFreshUrl, onError);
  const [rows, setRows] = useState<string[][]>([]);
  const [truncated, setTruncated] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    setIsLoading(true);
    fetchPreviewText(previewUrl, controller.signal)
      .then(({ text: loadedText, truncated: wasTruncated }) => {
        if (controller.signal.aborted) return;
        let text = loadedText;
        if (wasTruncated && !text.endsWith("\n")) {
          const finalCompleteRow = text.lastIndexOf("\n");
          text = finalCompleteRow < 0 ? "" : text.slice(0, finalCompleteRow + 1);
        }
        const parsed = Papa.parse<string[]>(text, {
          delimiter: name.toLowerCase().endsWith(".tsv") ? "\t" : "",
          skipEmptyLines: true,
        });
        if (parsed.errors.length > 0 && parsed.data.length === 0) throw new Error(parsed.errors[0].message);
        setRows(parsed.data);
        setTruncated(wasTruncated);
      })
      .catch(() => {
        if (!controller.signal.aborted) void retry();
      })
      .finally(() => {
        if (!controller.signal.aborted) setIsLoading(false);
      });
    return () => controller.abort();
  }, [previewUrl, retryVersion, retry, name]);

  if (isLoading) return <PreviewLoading />;
  const [headers = [], ...dataRows] = rows;

  return (
    <div className="w-full min-w-0">
      {truncated && <p className="mb-2 text-xs text-amber-700">Showing first 500 KB</p>}
      <div className="max-h-[70vh] max-w-full overflow-auto rounded border border-gray-200">
        <table className="min-w-full border-collapse text-left text-sm">
          <thead className="sticky top-0 bg-gray-100">
            <tr>{headers.map((header, index) => <th key={index} scope="col" className="border-b px-3 py-2 font-medium">{header}</th>)}</tr>
          </thead>
          <tbody>
            {dataRows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-white even:bg-gray-50">
                {headers.map((_, columnIndex) => <td key={columnIndex} className="max-w-xs break-all border-b px-3 py-2">{row[columnIndex] ?? ""}</td>)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
