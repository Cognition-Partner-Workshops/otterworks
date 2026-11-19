import { useState } from 'react';
import { NavLink, Navigate, Outlet } from 'react-router-dom';
import { BarChart3, Bell, ChevronLeft, ChevronRight, Database, FileClock, Flag, HeartPulse, LayoutDashboard, LogOut, MoreVertical, Repeat, TriangleAlert, UserCircle, Users } from 'lucide-react';
import otterLogo from '@/assets/otter-logo.png';
import { logout } from '../api';
import { storedUser } from '../auth';

export const legacyUrl = (import.meta.env.VITE_ADMIN_LEGACY_URL || 'http://localhost:4200').replace(/\/$/, '');
const items = [
  ['Dashboard', '/', LayoutDashboard], ['Users', '/users', Users], ['Audit Logs', '/audit', FileClock],
  ['Feature Flags', '/features', Flag], ['System Health', '/health', HeartPulse], ['Announcements', '/announcements', Bell],
  ['Storage Quotas', '/quotas', Database], ['Incidents', '/incidents', TriangleAlert], ['Analytics', '/analytics', BarChart3], ['Migration', '/migration', Repeat],
] as const;
export function Spinner() {
  return <div className="flex justify-center p-[60px]"><span role="progressbar" aria-label="Loading" className="block h-10 w-10 animate-spin rounded-full border-4 border-gray-200 border-t-[#1976d2]" /></div>;
}
export default function Shell() {
  const [collapsed, setCollapsed] = useState(false);
  const [menu, setMenu] = useState(false);
  if (!localStorage.getItem('ow_admin_token')) return <Navigate to="/admin/login" replace />;
  return <div className="flex min-h-screen text-[#333]">
    <aside className={`shrink-0 bg-[#1f3a5f] text-white ${collapsed ? 'w-[68px]' : 'w-[260px]'}`}>
      <div className="flex h-16 items-center justify-between border-b border-white/10 p-4">
        {!collapsed && <strong className="flex items-center gap-2 text-lg"><img src={otterLogo} alt="OtterWorks logo" width={28} height={28} />OtterWorks</strong>}
        <button aria-label={collapsed ? 'Expand' : 'Collapse'} onClick={() => setCollapsed(!collapsed)}>{collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}</button>
      </div>
      <nav className="py-2">{items.map(([label, path, Icon], index) => {
        const content = <><Icon size={20} />{!collapsed && <span>{label}</span>}</>;
        const classes = 'mx-2 my-1 flex items-center gap-4 rounded-sm p-3 hover:bg-white/10';
        return index < 2 ? <NavLink key={path} end={index === 0} to={`/admin${path === '/' ? '' : path}`} title={collapsed ? label : undefined} className={({ isActive }) => `${classes} ${isActive ? 'bg-[#d99a3d]/20 text-[#d99a3d]' : 'text-white/75'}`}>{content}</NavLink> : <a key={path} href={`${legacyUrl}${path}`} title={collapsed ? label : undefined} className={`${classes} text-white/75`}>{content}</a>;
      })}</nav>
    </aside>
    <div className="min-w-0 flex-1">
      <header className="relative flex h-16 items-center gap-3 border-b bg-white px-6 shadow-sm">
        <span className="flex-1 text-lg">Admin Dashboard</span><UserCircle size={20} /><span>{storedUser()?.displayName}</span>
        <button aria-label="User menu" onClick={() => setMenu(!menu)}><MoreVertical size={20} /></button>
        {menu && <button className="absolute right-4 top-14 z-20 flex gap-2 rounded bg-white p-4 shadow-lg" onClick={logout}><LogOut size={18} />Logout</button>}
      </header>
      <main className="min-h-[calc(100vh-64px)] bg-[#f5f5f5] p-6"><Outlet /></main>
    </div>
  </div>;
}
