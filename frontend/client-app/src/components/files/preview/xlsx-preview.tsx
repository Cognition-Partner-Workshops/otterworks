import * as XLSX from "xlsx";
import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { MAX_TABLE_ROWS } from "@/lib/preview-kind";
import type { PreviewRendererProps } from "./preview-types";
import { usePreviewRetry } from "./use-preview-retry";
import { PreviewLoading } from "./preview-loading";

export function XlsxPreview({ url, retryWithFreshUrl, onError }: PreviewRendererProps) {
  const preview = usePreviewRetry(url, retryWithFreshUrl, onError);
  const [searchParams, setSearchParams] = useSearchParams();
  const response = useXlsxWorkbook(preview.url, preview.retryVersion, preview.retry);
  if (response.isLoading) return <PreviewLoading />;
  if (!response.workbook) return null;

  const workbook = response.workbook;
  const requestedSheet = searchParams.get("sheet");
  const activeSheet = requestedSheet && workbook.SheetNames.includes(requestedSheet)
    ? requestedSheet
    : workbook.SheetNames[0];
  const worksheet = workbook.Sheets[activeSheet];
  const fullRange = worksheet?.["!fullref"] ?? worksheet?.["!ref"];
  const totalRows = fullRange ? XLSX.utils.decode_range(fullRange).e.r + 1 : 0;
  const rows = worksheet
    ? XLSX.utils.sheet_to_json<unknown[]>(worksheet, { header: 1, blankrows: false, defval: "" })
      .slice(0, MAX_TABLE_ROWS)
    : [];
  const isTruncated = totalRows > MAX_TABLE_ROWS;

  const selectSheet = (sheet: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("sheet", sheet);
    setSearchParams(next, { replace: true });
  };

  return (
    <div className="w-full min-w-0">
      <div role="tablist" aria-label="Worksheets" className="mb-3 flex gap-1 overflow-x-auto">
        {workbook.SheetNames.map((sheet) => (
          <button
            key={sheet}
            type="button"
            role="tab"
            aria-selected={activeSheet === sheet}
            onClick={() => selectSheet(sheet)}
            className="shrink-0 rounded px-3 py-2 text-sm hover:bg-gray-100"
          >
            {sheet}
          </button>
        ))}
      </div>
      {isTruncated && <p className="mb-2 text-xs text-amber-700">Showing first 1,000 rows</p>}
      <div className="max-h-[70vh] max-w-full overflow-auto rounded border border-gray-200">
        <table className="min-w-full border-collapse text-left text-sm">
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-white even:bg-gray-50">
                {row.map((value, columnIndex) => rowIndex === 0 ? (
                  <th key={columnIndex} scope="col" className="border-b px-3 py-2 font-medium">
                    {String(value)}
                  </th>
                ) : (
                  <td key={columnIndex} className="border-b px-3 py-2">{String(value)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function useXlsxWorkbook(url: string, retryVersion: number, retry: () => Promise<void>) {
  const [state, setState] = useState<{ isLoading: boolean; workbook?: XLSX.WorkBook }>({
    isLoading: true,
  });
  useEffect(() => {
    const controller = new AbortController();
    setState({ isLoading: true });
    fetch(url, { signal: controller.signal })
      .then((response) => {
        if (!response.ok) throw new Error(`XLSX preview failed with status ${response.status}`);
        return response.arrayBuffer();
      })
      .then((buffer) => XLSX.read(buffer, { type: "array", sheetRows: MAX_TABLE_ROWS + 1 }))
      .then((workbook) => {
        if (!controller.signal.aborted) setState({ isLoading: false, workbook });
      })
      .catch(() => {
        if (!controller.signal.aborted) void retry();
      });
    return () => controller.abort();
  }, [url, retryVersion, retry]);
  return state;
}
