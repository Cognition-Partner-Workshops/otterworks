import { ArrowDown, ArrowUp, UserCircle } from "lucide-react";
import type { User } from "../../api";
import { RowActionsMenu, type UserAction } from "./RowActionsMenu";

export type SortKey =
  "displayName" | "role" | "status" | "department" | "lastLogin";

const headers: [SortKey, string][] = [
  ["displayName", "Name"],
  ["role", "Role"],
  ["status", "Status"],
  ["department", "Department"],
  ["lastLogin", "Last Login"],
];
const chipColors: Record<string, string> = {
  admin: "bg-blue-50 text-blue-800",
  editor: "bg-green-50 text-green-800",
  viewer: "bg-purple-50 text-purple-800",
  active: "bg-green-50 text-green-800",
  suspended: "bg-red-50 text-red-800",
  pending: "bg-orange-50 text-orange-800",
};

function Chip({ value }: { value: string }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-wide ${chipColors[value] ?? ""}`}
    >
      {value}
    </span>
  );
}

function shortDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    year: "2-digit",
    month: "numeric",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date(value));
}

interface UsersTableProps {
  users: User[];
  sort: { key: SortKey; direction: "asc" | "desc" } | null;
  menu: string | null;
  changeSort: (key: SortKey) => void;
  setMenu: (id: string | null) => void;
  onView: (user: User) => void;
  onAction: (user: User, action: UserAction) => void;
}

export function UsersTable({
  users,
  sort,
  menu,
  changeSort,
  setMenu,
  onView,
  onAction,
}: UsersTableProps) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left">
        <thead>
          <tr className="h-12 border-b">
            {headers.map(([key, label]) => (
              <th
                key={key}
                className="px-4 font-medium"
                aria-sort={
                  sort?.key === key
                    ? sort.direction === "asc"
                      ? "ascending"
                      : "descending"
                    : "none"
                }
              >
                <button
                  onClick={() => changeSort(key)}
                  className="flex items-center gap-1"
                >
                  {label}
                  {sort?.key === key &&
                    (sort.direction === "asc" ? (
                      <ArrowUp size={14} />
                    ) : (
                      <ArrowDown size={14} />
                    ))}
                </button>
              </th>
            ))}
            <th className="px-4 font-medium">Actions</th>
          </tr>
        </thead>
        <tbody>
          {users.map((user) => (
            <tr
              key={user.id}
              className="h-12 cursor-pointer border-b hover:bg-gray-50"
              onClick={() => onView(user)}
            >
              <td className="px-4 py-1">
                <div className="flex items-center gap-3">
                  <UserCircle size={36} className="text-gray-400" />
                  <div>
                    <div className="user-name font-medium">
                      {user.displayName}
                    </div>
                    <div className="text-xs text-gray-400">{user.email}</div>
                  </div>
                </div>
              </td>
              <td className="px-4 py-1">
                <Chip value={user.role} />
              </td>
              <td className="px-4 py-1">
                <Chip value={user.status} />
              </td>
              <td className="px-4 py-1">{user.department || "-"}</td>
              <td className="px-4 py-1">
                {user.lastLogin ? shortDate(user.lastLogin) : "Never"}
              </td>
              <td className="px-4 py-1" onClick={(e) => e.stopPropagation()}>
                <RowActionsMenu
                  user={user}
                  menu={menu}
                  setMenu={setMenu}
                  onView={() => onView(user)}
                  onAction={(action) => onAction(user, action)}
                />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
