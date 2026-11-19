import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Area, AreaChart, Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts';
import { Cloud, FileText, Monitor, TrendingDown, TrendingUp, Users } from 'lucide-react';
import { getSummary, mapAnalyticsReport, mapDashboardStats, statsChanged } from '../api';
import { Spinner } from '../layout/Shell';

export default function Dashboard() {
  const stats = useQuery({ queryKey: ['admin', 'stats'], queryFn: async () => mapDashboardStats(await getSummary()), retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: false });
  const charts = useQuery({ queryKey: ['admin', 'charts'], queryFn: async () => mapAnalyticsReport(await getSummary()), retry: false, gcTime: 0, staleTime: 0, refetchOnMount: 'always', refetchOnWindowFocus: false });
  const { refetch } = stats;
  useEffect(() => {
    const refresh = () => { void refetch(); };
    statsChanged.addEventListener('change', refresh);
    return () => statsChanged.removeEventListener('change', refresh);
  }, [refetch]);
  const cards = stats.data ? [
    ['Total Users', stats.data.totalUsers.toLocaleString('en-US'), stats.data.usersGrowth, Users, 'bg-blue-50 text-blue-700'],
    ['Active Documents', stats.data.activeDocuments.toLocaleString('en-US'), stats.data.documentsGrowth, FileText, 'bg-green-50 text-green-700'],
    ['Storage Used', stats.data.storageUsed, stats.data.storageGrowth, Cloud, 'bg-orange-50 text-orange-600'],
    ['Active Sessions', stats.data.activeSessions.toLocaleString('en-US'), stats.data.sessionsGrowth, Monitor, 'bg-purple-50 text-purple-700'],
  ] as const : [];
  return <><h1 className="mb-6 text-2xl font-semibold">Dashboard</h1>
    {!stats.data ? <Spinner /> : <>
      <div className="mb-6 grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-5">{cards.map(([label, value, growth, Icon, color]) => <section key={label} className="flex flex-col items-center gap-3 rounded bg-white p-5 shadow">
        <Icon size={64} className={`rounded-xl p-3 ${color}`} /><div>
          <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p><p className="stat-value text-3xl font-bold">{value}</p>
          <p className={`flex items-center text-xs ${growth > 0 ? 'text-green-700' : growth < 0 ? 'text-red-600' : ''}`}>{growth > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}{growth}%</p>
        </div>
      </section>)}</div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(350px,1fr))] gap-5">
        <section className="rounded bg-white p-6 shadow"><h2 className="mb-4 text-xl font-medium">User Signups</h2><ResponsiveContainer width="100%" height={250}><AreaChart data={charts.data?.userSignups ?? []}><CartesianGrid stroke="#eee" /><XAxis dataKey="label" /><YAxis domain={[0, 'auto']} /><Tooltip /><Area type="monotone" dataKey="value" stroke="#1976d2" fill="rgba(25,118,210,0.1)" /></AreaChart></ResponsiveContainer></section>
        <section className="rounded bg-white p-6 shadow"><h2 className="mb-4 text-xl font-medium">Document Activity</h2><ResponsiveContainer width="100%" height={250}><BarChart data={charts.data?.documentActivity ?? []}><CartesianGrid stroke="#eee" /><XAxis dataKey="label" /><YAxis domain={[0, 'auto']} /><Tooltip /><Bar dataKey="value" fill="#4fc3f7" radius={[4,4,0,0]} /></BarChart></ResponsiveContainer></section>
      </div>
    </>}
  </>;
}
