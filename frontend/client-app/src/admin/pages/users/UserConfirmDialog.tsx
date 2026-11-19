import { useEffect, useRef } from "react";
import type { User } from "../../api";

interface UserConfirmation {
  user: User;
  action: "Suspend" | "Delete";
}

interface UserConfirmDialogProps {
  dialog: UserConfirmation | null;
  onCancel: () => void;
  onConfirm: (user: User, action: "Suspend" | "Delete") => void;
}

export function UserConfirmDialog({
  dialog,
  onCancel,
  onConfirm,
}: UserConfirmDialogProps) {
  const dialogRef = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    if (dialog) {
      dialogRef.current?.showModal();
    } else {
      dialogRef.current?.close();
    }
  }, [dialog]);

  return (
    <dialog
      ref={dialogRef}
      onCancel={onCancel}
      onClick={(event) => {
        if (event.target === event.currentTarget) {
          onCancel();
        }
      }}
      className="max-w-lg rounded bg-white p-6 shadow-xl backdrop:bg-black/40"
    >
      {dialog && (
        <>
          <h2 className="mb-5 text-xl font-medium">{dialog.action} User</h2>
          <p className="leading-relaxed text-gray-600">
            {dialog.action === "Suspend"
              ? `Are you sure you want to suspend ${dialog.user.displayName}?`
              : `Are you sure you want to permanently delete ${dialog.user.displayName}? This action cannot be undone.`}
          </p>
          <div className="mt-6 flex justify-end gap-4">
            <button onClick={onCancel}>Cancel</button>
            <button
              className="rounded bg-red-600 px-5 py-2 text-white"
              onClick={() => onConfirm(dialog.user, dialog.action)}
            >
              {dialog.action}
            </button>
          </div>
        </>
      )}
    </dialog>
  );
}
