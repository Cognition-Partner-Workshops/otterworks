import type { PreviewRendererProps } from "./preview-types";

export function PdfPreview({ url, fileName }: PreviewRendererProps & { fileName: string }) {
  return (
    <div className="w-full">
      <div className="mb-3 text-right">
        <a
          href={url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-sm text-otter-600 hover:underline"
        >
          Open in new tab
        </a>
      </div>
      <iframe
        src={url}
        title={fileName}
        className="h-[70vh] w-full rounded border border-gray-200 bg-white"
      />
    </div>
  );
}
