import { useState } from "react";
import { LogOut, MoreVertical, UserCircle } from "lucide-react";
import { logout } from "../api";
import { storedUser } from "../auth";

export function Toolbar() {
  const [menu, setMenu] = useState(false);
  return (
    <header className="relative flex h-16 items-center gap-3 border-b bg-white px-6 shadow-sm">
      <span className="flex-1 text-lg">Admin Dashboard</span>
      <UserCircle size={20} />
      <span>{storedUser()?.displayName}</span>
      <button aria-label="User menu" onClick={() => setMenu(!menu)}>
        <MoreVertical size={20} />
      </button>
      {menu && (
        <button
          className="absolute right-4 top-14 z-20 flex gap-2 rounded bg-white p-4 shadow-lg"
          onClick={logout}
        >
          <LogOut size={18} />
          Logout
        </button>
      )}
    </header>
  );
}
