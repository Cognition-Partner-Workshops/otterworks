import { useEffect, useId, useRef, useCallback, type ReactNode } from "react";
import { AlertTriangle, Trash2 } from "lucide-react";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  description: ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: "destructive" | "default";
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  variant = "default",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const cancelRef = useRef<HTMLButtonElement>(null);
  const dialogRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
        return;
      }
      if (e.key === "Tab" && dialogRef.current) {
        const focusable = dialogRef.current.querySelectorAll<HTMLElement>(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length === 0) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        if (!dialogRef.current.contains(document.activeElement)) {
          e.preventDefault();
          first.focus();
        } else if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    },
    [onCancel]
  );

  useEffect(() => {
    if (open) {
      const previouslyFocused = document.activeElement as HTMLElement | null;
      document.addEventListener("keydown", handleKeyDown);
      cancelRef.current?.focus();
      return () => {
        document.removeEventListener("keydown", handleKeyDown);
        previouslyFocused?.focus?.();
      };
    }
  }, [open, handleKeyDown]);

  if (!open) return null;

  const isDestructive = variant === "destructive";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role={isDestructive ? "alertdialog" : "dialog"}
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/50 transition-opacity"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div
        ref={dialogRef}
        className="relative bg-white rounded-xl shadow-xl max-w-md w-full mx-4 p-6 space-y-4"
      >
        <div className="flex items-start gap-4">
          {isDestructive && (
            <div className="w-10 h-10 rounded-full bg-red-100 flex items-center justify-center flex-shrink-0">
              <AlertTriangle size={20} className="text-red-600" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h2 id={titleId} className="text-lg font-semibold text-gray-900">
              {title}
            </h2>
            <p id={descriptionId} className="text-sm text-gray-500 mt-1 break-words">
              {description}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-2">
          <button
            ref={cancelRef}
            type="button"
            onClick={onCancel}
            className="px-4 py-2 text-sm font-medium text-gray-700 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-otter-500 focus-visible:ring-offset-2"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            onClick={onConfirm}
            data-variant={variant}
            className={
              isDestructive
                ? "flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-red-600 rounded-lg hover:bg-red-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-red-500 focus-visible:ring-offset-2"
                : "px-4 py-2 text-sm font-medium text-white bg-otter-600 rounded-lg hover:bg-otter-700 transition focus:outline-none focus-visible:ring-2 focus-visible:ring-otter-500 focus-visible:ring-offset-2"
            }
          >
            {isDestructive && <Trash2 size={16} aria-hidden="true" />}
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
