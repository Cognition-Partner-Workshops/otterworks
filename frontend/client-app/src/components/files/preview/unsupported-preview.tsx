import { File } from "lucide-react";
import { formatFileSize } from "@/lib/utils";

export function UnsupportedPreview({
  name,
  size,
  mimeType,
  onDownload,
}: {
  name: string;
  size: number;
  mimeType: string;
  onDownload: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <File size={40} className="text-gray-400" aria-hidden="true" />
      <p className="font-medium text-gray-900">{name}</p>
      <p className="text-sm text-gray-500">{formatFileSize(size)} · {mimeType || "Unknown file type"}</p>
      <p className="text-sm text-gray-600">Preview isn't available for this file type</p>
      <button
        type="button"
        onClick={onDownload}
        className="rounded-lg bg-otter-600 px-4 py-2 text-sm font-medium text-white hover:bg-otter-700"
      >
        Download
      </button>
    </div>
  );
}
