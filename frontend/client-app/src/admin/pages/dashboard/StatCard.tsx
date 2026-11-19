import { TrendingDown, TrendingUp, type LucideIcon } from "lucide-react";

interface StatCardProps {
  label: string;
  value: string;
  growth: number;
  Icon: LucideIcon;
  color: string;
}

export function StatCard({ label, value, growth, Icon, color }: StatCardProps) {
  return (
    <section className="flex flex-col items-center gap-3 rounded bg-white p-5 shadow">
      <Icon size={64} className={`rounded-xl p-3 ${color}`} />
      <div>
        <p className="text-xs uppercase tracking-wide text-gray-400">{label}</p>
        <p className="stat-value text-3xl font-bold">{value}</p>
        <p
          className={`flex items-center text-xs ${growth > 0 ? "text-green-700" : growth < 0 ? "text-red-600" : ""}`}
        >
          {growth > 0 ? <TrendingUp size={16} /> : <TrendingDown size={16} />}
          {growth}%
        </p>
      </div>
    </section>
  );
}
