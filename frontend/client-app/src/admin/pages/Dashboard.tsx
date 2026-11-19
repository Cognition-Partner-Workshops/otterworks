import { useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import { Cloud, FileText, Monitor, Users } from "lucide-react";
import {
  getSummary,
  mapAnalyticsReport,
  mapDashboardStats,
  statsChanged,
} from "../api";
import { Spinner } from "../layout/Spinner";
import { StatCard } from "./dashboard/StatCard";
import { DashboardCharts } from "./dashboard/DashboardCharts";

export default function Dashboard() {
  const stats = useQuery({
    queryKey: ["admin", "stats"],
    queryFn: async () => mapDashboardStats(await getSummary()),
    retry: false,
    gcTime: 0,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
  });
  const charts = useQuery({
    queryKey: ["admin", "charts"],
    queryFn: async () => mapAnalyticsReport(await getSummary()),
    retry: false,
    gcTime: 0,
    staleTime: 0,
    refetchOnMount: "always",
    refetchOnWindowFocus: false,
  });
  const { refetch } = stats;
  useEffect(() => {
    const refresh = () => {
      void refetch();
    };
    statsChanged.addEventListener("change", refresh);
    return () => statsChanged.removeEventListener("change", refresh);
  }, [refetch]);
  const cards = stats.data
    ? ([
        [
          "Total Users",
          stats.data.totalUsers.toLocaleString("en-US"),
          stats.data.usersGrowth,
          Users,
          "bg-blue-50 text-blue-700",
        ],
        [
          "Active Documents",
          stats.data.activeDocuments.toLocaleString("en-US"),
          stats.data.documentsGrowth,
          FileText,
          "bg-green-50 text-green-700",
        ],
        [
          "Storage Used",
          stats.data.storageUsed,
          stats.data.storageGrowth,
          Cloud,
          "bg-orange-50 text-orange-600",
        ],
        [
          "Active Sessions",
          stats.data.activeSessions.toLocaleString("en-US"),
          stats.data.sessionsGrowth,
          Monitor,
          "bg-purple-50 text-purple-700",
        ],
      ] as const)
    : [];
  return (
    <>
      <h1 className="mb-6 text-2xl font-semibold">Dashboard</h1>
      {!stats.data ? (
        <Spinner />
      ) : (
        <>
          <div className="mb-6 grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-5">
            {cards.map(([label, value, growth, Icon, color]) => (
              <StatCard
                key={label}
                label={label}
                value={value}
                growth={growth}
                Icon={Icon}
                color={color}
              />
            ))}
          </div>
          <DashboardCharts report={charts.data} />
        </>
      )}
    </>
  );
}
