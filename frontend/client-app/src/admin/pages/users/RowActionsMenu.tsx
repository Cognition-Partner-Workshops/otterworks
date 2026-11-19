import { MoreVertical } from "lucide-react";
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
  return (
    <>
      <button
        aria-label="User actions"
        onClick={() => setMenu(menu === user.id ? null : user.id)}
      >
        <MoreVertical size={20} />
      </button>
      {menu === user.id && (
        <>
          <button
            aria-label="Close user actions"
            className="fixed inset-0 z-10 cursor-default"
            onClick={() => setMenu(null)}
          />
          <div
            role="menu"
            className="absolute right-4 top-10 z-20 min-w-40 rounded bg-white py-2 shadow-xl"
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
        </>
      )}
    </>
  );
}
