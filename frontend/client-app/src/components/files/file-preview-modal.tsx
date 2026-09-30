import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { X, Download, ExternalLink, AlertCircle, Maximize2 } from "lucide-react";
import { FilePreview } from "@/components/files/file-preview";
import { filesApi } from "@/lib/api";
import { formatFileSize } from "@/lib/utils";
import { getPreviewKind, PREVIEW_KIND_LABELS } from "@/lib/file-preview";
import type { FileItem } from "@/types";

interface FilePreviewModalProps {
  file: FileItem;
  onClose: () => void;
  onDownload?: (id: string, name: string) => void;
}

export function FilePreviewModal({ file, onClose, onDownload }: FilePreviewModalProps) {
  const closeRef = useRef<HTMLButtonElement>(null);

  const {
    data: presignedUrl,
    isLoading: isUrlLoading,
    isError,
  } = useQuery({
    queryKey: ["files", file.id, "download-url"],
    queryFn: () => filesApi.getDownloadUrl(file.id),
    staleTime: 30 * 60 * 1000,
  });

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        onClose();
      }
    };
    document.addEventListener("keydown", onKeyDown);
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeRef.current?.focus();
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  const kindLabel = PREVIEW_KIND_LABELS[getPreviewKind(file.mimeType, file.name)];
  const handleDownload = onDownload ? () => onDownload(file.id, file.name) : undefined;

  return createPortal(
    <>
      <div className="fixed inset-0 bg-black/50 z-40" onClick={onClose} />
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none">
        <div
          role="dialog"
          aria-modal="true"
          aria-label={`Preview of ${file.name}`}
          className="pointer-events-auto bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] flex flex-col"
          onClick={(e) => e.stopPropagation()}
        >
          <div className="flex items-center justify-between gap-4 px-5 py-4 border-b border-gray-200">
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-gray-900 truncate">{file.name}</h2>
              <p className="text-xs text-gray-400 truncate">
                {kindLabel} · {formatFileSize(file.size)}
                {file.mimeType ? ` · ${file.mimeType}` : ""}
              </p>
            </div>
            <div className="flex items-center gap-1 flex-shrink-0">
              <Link
                to={`/files/${file.id}`}
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                aria-label="Open details"
                title="Open details"
              >
                <Maximize2 size={18} />
              </Link>
              {presignedUrl && (
                <a
                  href={presignedUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                  aria-label="Open in new tab"
                  title="Open in new tab"
                >
                  <ExternalLink size={18} />
                </a>
              )}
              {handleDownload && (
                <button
                  onClick={handleDownload}
                  className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                  aria-label="Download"
                  title="Download"
                >
                  <Download size={18} />
                </button>
              )}
              <button
                ref={closeRef}
                onClick={onClose}
                className="p-2 rounded-lg hover:bg-gray-100 text-gray-500"
                aria-label="Close preview"
                title="Close (Esc)"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          <div className="flex-1 overflow-auto p-6 flex items-center justify-center bg-gray-50 min-h-[300px] rounded-b-2xl">
            {isError ? (
              <div className="text-center py-8">
                <AlertCircle size={48} className="text-gray-300 mx-auto mb-3" />
                <p className="text-sm text-gray-500">Couldn&apos;t load a preview for this file</p>
              </div>
            ) : (
              <FilePreview
                fileName={file.name}
                mimeType={file.mimeType}
                presignedUrl={presignedUrl}
                isUrlLoading={isUrlLoading}
                onDownload={handleDownload}
              />
            )}
          </div>
        </div>
      </div>
    </>,
    document.body
  );
}
