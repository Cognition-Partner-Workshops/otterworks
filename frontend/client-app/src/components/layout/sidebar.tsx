import { Link, useLocation } from "react-router-dom";
import {
  Home,
  Clock,
  FolderOpen,
  FileText,
  Search,
  Bell,
  Settings,
  Share2,
  Trash2,
  Star,
  Menu,
  X,
  Plus,
  LogOut,
  type LucideIcon,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";
import { getInitials } from "@/lib/utils";
import { Logo } from "@/components/ui/logo";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

const navGroups: NavGroup[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: Home },
      { href: "/recent", label: "Recent", icon: Clock },
      { href: "/files", label: "Files", icon: FolderOpen },
      { href: "/documents", label: "Documents", icon: FileText },
      { href: "/search", label: "Search", icon: Search },
    ],
  },
  {
    label: "Collaboration",
    items: [
      { href: "/shared", label: "Shared with me", icon: Share2 },
      { href: "/starred", label: "Starred", icon: Star },
      { href: "/notifications", label: "Notifications", icon: Bell },
    ],
  },
  {
    label: "System",
    items: [
      { href: "/trash", label: "Trash", icon: Trash2 },
      { href: "/settings", label: "Settings", icon: Settings },
    ],
  },
];

export function Sidebar() {
  const { pathname } = useLocation();
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { user, logout } = useAuthStore();

  return (
    <>
      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggleSidebar}
        />
      )}

      <aside
        className={cn(
          "fixed top-0 left-0 z-50 flex h-full flex-col border-r border-[#ddd] bg-white text-[#012169] transition-transform duration-200",
          "w-64",
          sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0 lg:w-16"
        )}
      >
        {/* Header */}
        <div
          className={cn(
            "flex border-b border-[#ddd]",
            sidebarOpen
              ? "h-12 items-center justify-between px-3"
              : "h-20 flex-col items-center justify-center gap-1 py-1"
          )}
        >
          <Link
            to="/dashboard"
            aria-label="Document Center"
            className={cn("flex items-center", sidebarOpen ? "gap-2" : "justify-center")}
          >
            <Logo size={28} />
            {sidebarOpen && (
              <span className="text-sm font-semibold text-[#012169]">Document Center</span>
            )}
          </Link>
          <button
            onClick={toggleSidebar}
            className={cn(
              "rounded text-gray-600 hover:bg-gray-100 hover:text-[#012169]",
              sidebarOpen ? "p-2" : "p-1"
            )}
            aria-label="Toggle sidebar"
          >
            {sidebarOpen ? <X size={18} /> : <Menu size={18} />}
          </button>
        </div>

        {/* New button */}
        {sidebarOpen && (
          <div className="p-3">
            <Link
              to="/files"
              className="flex w-full items-center justify-center gap-2 bg-accent-500 text-white transition hover:bg-accent-600 text-sm"
            >
              <Plus size={16} />
              New
            </Link>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 px-2 py-1 overflow-y-auto">
          {navGroups.map((group) => (
            <div key={group.label} className="mb-2">
              {sidebarOpen && (
                <p className="px-3 pt-2 pb-1 text-[11px] font-semibold uppercase tracking-wider text-gray-500">
                  {group.label}
                </p>
              )}
              <ul className="space-y-0.5">
                {group.items.map((item) => {
                  const isActive =
                    pathname === item.href || pathname.startsWith(item.href + "/");
                  return (
                    <li key={item.href}>
                      <Link
                        to={item.href}
                        className={cn(
                          "flex items-center gap-3 border-l-[3px] px-3 py-1.5 text-sm transition",
                          isActive
                            ? "border-accent-500 bg-[#f5f5f5] font-semibold text-[#012169]"
                            : "border-transparent font-medium text-[#012169] hover:bg-[#f5f5f5]"
                        )}
                      >
                        <item.icon size={18} />
                        {sidebarOpen && <span>{item.label}</span>}
                      </Link>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </nav>

        {/* User profile */}
        <div className="border-t border-[#ddd] px-3 py-2">
          {user && sidebarOpen && (
            <div className="flex items-center gap-3 px-1 py-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-otter-100 text-xs font-semibold text-[#012169]">
                {getInitials(user.displayName)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="truncate text-sm font-medium text-[#012169]">
                  {user.displayName}
                </p>
                <p className="truncate text-xs text-gray-500">{user.email}</p>
              </div>
              <button
                onClick={logout}
                className="rounded p-1.5 text-gray-600 hover:bg-gray-100 hover:text-[#012169]"
                aria-label="Sign out"
              >
                <LogOut size={16} />
              </button>
            </div>
          )}
        </div>
      </aside>
    </>
  );
}
