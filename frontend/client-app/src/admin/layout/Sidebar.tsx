import { useState } from "react";
import { NavLink } from "react-router-dom";
import {
  BarChart3,
  Bell,
  ChevronLeft,
  ChevronRight,
  Database,
  FileClock,
  Flag,
  HeartPulse,
  LayoutDashboard,
  Repeat,
  TriangleAlert,
  Users,
} from "lucide-react";
import otterLogo from "@/assets/otter-logo.png";

export const legacyUrl = (
  import.meta.env.VITE_ADMIN_LEGACY_URL || "http://localhost:4200"
).replace(/\/$/, "");

const items = [
  ["Dashboard", "/", LayoutDashboard],
  ["Users", "/users", Users],
  ["Audit Logs", "/audit", FileClock],
  ["Feature Flags", "/features", Flag],
  ["System Health", "/health", HeartPulse],
  ["Announcements", "/announcements", Bell],
  ["Storage Quotas", "/quotas", Database],
  ["Incidents", "/incidents", TriangleAlert],
  ["Analytics", "/analytics", BarChart3],
  ["Migration", "/migration", Repeat],
] as const;

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <aside
      className={`shrink-0 bg-[#1f3a5f] text-white ${collapsed ? "w-[68px]" : "w-[260px]"}`}
    >
      <div className="flex h-16 items-center justify-between border-b border-white/10 p-4">
        {!collapsed && (
          <strong className="flex items-center gap-2 text-lg">
            <img src={otterLogo} alt="OtterWorks logo" width={28} height={28} />
            OtterWorks
          </strong>
        )}
        <button
          aria-label={collapsed ? "Expand" : "Collapse"}
          onClick={() => setCollapsed(!collapsed)}
        >
          {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
        </button>
      </div>
      <nav className="py-2">
        {items.map(([label, path, Icon], index) => {
          const content = (
            <>
              <Icon size={20} />
              {!collapsed && <span>{label}</span>}
            </>
          );
          const classes =
            "mx-2 my-1 flex items-center gap-4 rounded-sm p-3 hover:bg-white/10";
          return index < 2 ? (
            <NavLink
              key={path}
              end={index === 0}
              to={`/admin${path === "/" ? "" : path}`}
              title={collapsed ? label : undefined}
              className={({ isActive }) =>
                `${classes} ${isActive ? "bg-[#d99a3d]/20 text-[#d99a3d]" : "text-white/75"}`
              }
            >
              {content}
            </NavLink>
          ) : (
            <a
              key={path}
              href={`${legacyUrl}${path}`}
              title={collapsed ? label : undefined}
              className={`${classes} text-white/75`}
            >
              {content}
            </a>
          );
        })}
      </nav>
    </aside>
  );
}
