import { MoreVertical } from "lucide-react";
import { useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { User } from "../../api";

export type UserAction = "Suspend" | "Restore" | "Delete";

interface RowActionsMenuProps {
  user: User;
  menu: string | null;
  setMenu: (id: string | null) => void;
  onView: () => void;
  onAction: (action: UserAction) => void;
}

export function RowActionsMenu({
  user,
  menu,
  setMenu,
  onView,
  onAction,
}: RowActionsMenuProps) {
  const triggerRef = useRef<HTMLButtonElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const open = menu === user.id;

  useLayoutEffect(() => {
    if (!open) return;

    const placeMenu = () => {
      const trigger = triggerRef.current?.getBoundingClientRect();
      const popup = menuRef.current?.getBoundingClientRect();
      if (!trigger || !popup) return;

      const margin = 8;
      const below = trigger.bottom + 4;
      const top =
        below + popup.height <= window.innerHeight - margin
          ? below
          : trigger.top - popup.height - 4;
      setPosition({
        top: Math.max(
          margin,
          Math.min(top, window.innerHeight - popup.height - margin)
        ),
        left: Math.max(
          margin,
          Math.min(
            trigger.right - popup.width,
            window.innerWidth - popup.width - margin
          )
        ),
      });
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenu(null);
        triggerRef.current?.focus();
      }
    };

    placeMenu();
    window.addEventListener("resize", placeMenu);
    window.addEventListener("scroll", placeMenu, true);
    window.addEventListener("keydown", closeOnEscape);
    return () => {
      window.removeEventListener("resize", placeMenu);
      window.removeEventListener("scroll", placeMenu, true);
      window.removeEventListener("keydown", closeOnEscape);
    };
  }, [open, setMenu, user.status]);

  return (
    <>
      <button
        ref={triggerRef}
        aria-label="User actions"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setMenu(menu === user.id ? null : user.id)}
      >
        <MoreVertical size={20} />
      </button>
      {open &&
        createPortal(
          <>
            <button
              aria-label="Close user actions"
              className="fixed inset-0 z-10 cursor-default"
              onClick={() => setMenu(null)}
            />
            <div
              ref={menuRef}
              role="menu"
              style={{
                ...position,
                maxHeight: "calc(100vh - 16px)",
                maxWidth: "calc(100vw - 16px)",
              }}
              className="fixed z-50 min-w-40 overflow-auto rounded bg-white py-2 shadow-xl"
            >
              <button
                role="menuitem"
                className="block w-full px-4 py-3 text-left hover:bg-gray-100"
                onClick={onView}
              >
                View Details
              </button>
              {user.status === "active" && (
                <button
                  role="menuitem"
                  className="block w-full px-4 py-3 text-left hover:bg-gray-100"
                  onClick={() => {
                    setMenu(null);
                    onAction("Suspend");
                  }}
                >
                  Suspend
                </button>
              )}
              {user.status === "suspended" && (
                <button
                  role="menuitem"
                  className="block w-full px-4 py-3 text-left hover:bg-gray-100"
                  onClick={() => onAction("Restore")}
                >
                  Restore
                </button>
              )}
              <button
                role="menuitem"
                className="block w-full px-4 py-3 text-left text-red-600 hover:bg-gray-100"
                onClick={() => {
                  setMenu(null);
                  onAction("Delete");
                }}
              >
                Delete
              </button>
            </div>
          </>,
          document.body
        )}
    </>
  );
}
