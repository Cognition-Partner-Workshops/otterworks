import { type ReactNode } from "react";
import { Sidebar } from "./sidebar";
import { Footer } from "./footer";
import { ConceptBanner } from "./concept-banner";
import { SearchBar } from "@/components/ui/search-bar";
import { BrandLockup } from "@/components/ui/brand-lockup";
import { NotificationBell } from "@/components/ui/notification-bell";
import { useUIStore } from "@/stores/ui-store";
import { useAuthStore } from "@/stores/auth-store";
import { cn } from "@/lib/utils";
import { Menu, HelpCircle } from "lucide-react";

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  const { sidebarOpen, toggleSidebar } = useUIStore();
  const { user } = useAuthStore();

  return (
    <div className="min-h-screen bg-[#f5f5f5]">
      <Sidebar />

      <div
        className={cn(
          "flex min-h-screen flex-col transition-all duration-200",
          sidebarOpen ? "lg:ml-64" : "lg:ml-16"
        )}
      >
        <ConceptBanner />
        {/* Top utility bar */}
        <header className="sticky top-0 z-30 h-12 border-b border-[#ddd] bg-white">
          <div className="flex items-center justify-between h-full px-3 lg:px-4">
            <div className="flex min-w-0 flex-1 items-center gap-3">
              <button
                onClick={toggleSidebar}
                className="p-2 rounded hover:bg-gray-100 text-gray-500 lg:hidden"
                aria-label="Open menu"
              >
                <Menu size={18} />
              </button>
              <div className="hidden shrink-0 lg:flex">
                <BrandLockup logoSize={28} />
              </div>
              <div className="w-full min-w-0 max-w-xl">
                <SearchBar />
              </div>
            </div>
            <div className="flex items-center gap-1 ml-4">
              <a
                href="/terms"
                className="p-2 rounded hover:bg-gray-100 text-gray-500"
                aria-label="Help"
                title="Help & legal"
              >
                <HelpCircle size={18} />
              </a>
              <NotificationBell />
              {user && (
                <span className="hidden lg:block px-2 text-xs text-gray-600 truncate max-w-[160px]">
                  {user.displayName}
                </span>
              )}
            </div>
          </div>
        </header>

        {/* Main content */}
        <main className="flex-1 p-4 lg:p-5">{children}</main>

        <Footer />
      </div>
    </div>
  );
}
