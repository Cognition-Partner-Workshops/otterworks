import { formatFileSize } from "@/lib/utils";

export function LargeFileGate({
  size,
  onLoad,
}: {
  size: number;
  onLoad: () => void;
}) {
  return (
    <div className="flex flex-col items-center gap-3 py-8 text-center">
      <p className="text-sm text-gray-700">Large file ({formatFileSize(size)})</p>
      <button
        type="button"
        onClick={onLoad}
        className="rounded-lg bg-otter-600 px-4 py-2 text-sm font-medium text-white hover:bg-otter-700"
      >
        Load preview
      </button>
    </div>
  );
}
