import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { AlertCircle, Check, Download, Loader2 } from "lucide-react";
import { cn } from "@/lib/utils";

export type DownloadStatus = "idle" | "downloading" | "done" | "error";

const DONE_RESET_MS = 3000;

const BASE_CLASS =
  "flex items-center gap-2 px-3 py-2 text-sm bg-white border rounded-lg transition disabled:opacity-50 disabled:cursor-not-allowed";

const STATUS_CLASS: Record<DownloadStatus, string> = {
  idle: "text-gray-700 border-gray-300 hover:bg-gray-50",
  downloading: "text-gray-700 border-gray-300",
  done: "text-green-700 border-green-300 bg-green-50 hover:bg-green-100",
  error: "text-red-600 border-red-200 hover:bg-red-50",
};

const STATUS_LABEL: Record<DownloadStatus, string> = {
  idle: "Download",
  downloading: "Downloading...",
  done: "Downloaded",
  error: "Retry download",
};

export function getDownloadErrorMessage(error: unknown): string {
  const data = (error as { response?: { data?: { error?: unknown; message?: unknown } } })
    ?.response?.data;
  if (typeof data?.error === "string" && data.error) return data.error;
  if (typeof data?.message === "string" && data.message) return data.message;
  if (error instanceof Error && error.message) return error.message;
  return "Unknown error";
}

function clickLink(href: string, fileName: string) {
  const a = document.createElement("a");
  a.href = href;
  a.download = fileName;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}

function saveBlob(blob: Blob, fileName: string) {
  const objectUrl = URL.createObjectURL(blob);
  clickLink(objectUrl, fileName);
  URL.revokeObjectURL(objectUrl);
}

// An opaque no-cors request only rejects when the storage host is unreachable, which
// separates "storage is down" from "storage does not send CORS headers".
async function isStorageReachable(url: string): Promise<boolean> {
  const controller = new AbortController();
  try {
    await fetch(url, { mode: "no-cors", signal: controller.signal });
    return true;
  } catch {
    return false;
  } finally {
    controller.abort();
  }
}

type DownloadOutcome = "saved" | "handed-off";

async function downloadFile(url: string, fileName: string): Promise<DownloadOutcome> {
  let response: Response;
  try {
    response = await fetch(url);
  } catch {
    if (!(await isStorageReachable(url))) {
      throw new Error("Could not reach file storage");
    }
    clickLink(url, fileName);
    return "handed-off";
  }
  if (!response.ok) {
    throw new Error(`Storage responded with ${response.status} ${response.statusText}`.trim());
  }
  saveBlob(await response.blob(), fileName);
  return "saved";
}

interface DownloadButtonProps {
  fileName: string;
  getDownloadUrl: () => Promise<string>;
}

export function DownloadButton({ fileName, getDownloadUrl }: Readonly<DownloadButtonProps>) {
  const [status, setStatus] = useState<DownloadStatus>("idle");
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const resetTimer = useRef<ReturnType<typeof setTimeout>>();

  useEffect(() => () => clearTimeout(resetTimer.current), []);

  const handleDownload = async () => {
    clearTimeout(resetTimer.current);
    setStatus("downloading");
    setErrorMessage(null);
    const toastId = toast.loading(`Downloading ${fileName}...`);
    try {
      const url = await getDownloadUrl();
      const outcome = await downloadFile(url, fileName);
      toast.success(
        outcome === "saved" ? `Downloaded ${fileName}` : `Download of ${fileName} started`,
        { id: toastId }
      );
      setStatus("done");
      resetTimer.current = setTimeout(() => setStatus("idle"), DONE_RESET_MS);
    } catch (error) {
      const message = getDownloadErrorMessage(error);
      toast.error(`Download failed: ${message}`, { id: toastId });
      setErrorMessage(message);
      setStatus("error");
    }
  };

  const Icon = {
    idle: Download,
    downloading: Loader2,
    done: Check,
    error: AlertCircle,
  }[status];

  return (
    <>
      <button
        type="button"
        onClick={handleDownload}
        disabled={status === "downloading"}
        aria-busy={status === "downloading"}
        title={status === "error" && errorMessage ? `Download failed: ${errorMessage}` : undefined}
        data-status={status}
        className={cn(BASE_CLASS, STATUS_CLASS[status])}
      >
        <Icon size={16} className={status === "downloading" ? "animate-spin" : undefined} />
        {STATUS_LABEL[status]}
      </button>
      <span role="status" aria-live="polite" className="sr-only">
        {status === "downloading" && `Downloading ${fileName}`}
        {status === "done" && `Downloaded ${fileName}`}
        {status === "error" && `Download failed: ${errorMessage}`}
      </span>
    </>
  );
}
