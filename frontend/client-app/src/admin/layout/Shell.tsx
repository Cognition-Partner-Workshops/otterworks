import { Outlet } from "react-router-dom";
import { AuthGuard } from "./AuthGuard";
import { Sidebar } from "./Sidebar";
import { Toolbar } from "./Toolbar";

export { legacyUrl } from "./Sidebar";

export default function Shell() {
  return (
    <AuthGuard>
      <div className="flex min-h-screen text-[#333]">
        <Sidebar />
        <div className="min-w-0 flex-1">
          <Toolbar />
          <main className="min-h-[calc(100vh-64px)] bg-[#f5f5f5] p-6">
            <Outlet />
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
