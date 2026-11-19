import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { mapAnalyticsReport } from "../../api";

interface DashboardChartsProps {
  report?: ReturnType<typeof mapAnalyticsReport>;
}

export function DashboardCharts({ report }: DashboardChartsProps) {
  return (
    <div className="grid grid-cols-[repeat(auto-fit,minmax(350px,1fr))] gap-5">
      <section className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 text-xl font-medium">User Signups</h2>
        <ResponsiveContainer width="100%" height={200}>
          <AreaChart data={report?.userSignups ?? []}>
            <CartesianGrid stroke="#eee" />
            <XAxis dataKey="label" />
            <YAxis domain={[0, "auto"]} />
            <Tooltip />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#1976d2"
              fill="rgba(25,118,210,0.1)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </section>
      <section className="rounded bg-white p-4 shadow">
        <h2 className="mb-2 text-xl font-medium">Document Activity</h2>
        <ResponsiveContainer width="100%" height={200}>
          <BarChart data={report?.documentActivity ?? []}>
            <CartesianGrid stroke="#eee" />
            <XAxis dataKey="label" />
            <YAxis domain={[0, "auto"]} />
            <Tooltip />
            <Bar dataKey="value" fill="#4fc3f7" radius={[4, 4, 0, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </section>
    </div>
  );
}
