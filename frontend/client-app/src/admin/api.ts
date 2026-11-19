import axios from "axios";

export const adminApi = axios.create({ baseURL: "/api/v1" });

export function logout() {
  localStorage.removeItem("ow_admin_token");
  localStorage.removeItem("ow_admin_user");
  window.location.assign("/admin/login");
}
adminApi.interceptors.request.use((config) => {
  const token = localStorage.getItem("ow_admin_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});
adminApi.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      if (error.config?.url === "/auth/login") {
        localStorage.removeItem("ow_admin_token");
        localStorage.removeItem("ow_admin_user");
      } else logout();
    }
    return Promise.reject(error);
  }
);

export interface RawUser {
  id: string;
  email: string;
  display_name: string;
  role: string;
  status: string;
  avatar_url?: string;
  last_login_at?: string | null;
  created_at: string;
  storage_quota?: { used_bytes?: number; quota_bytes?: number };
  metadata?: { department?: string; documents_count?: number };
}

export function mapUser(raw: RawUser) {
  return {
    id: raw.id,
    email: raw.email,
    displayName: raw.display_name,
    role: raw.role,
    status: raw.status,
    avatarUrl: raw.avatar_url,
    storageUsed: raw.storage_quota?.used_bytes ?? 0,
    storageQuota: raw.storage_quota?.quota_bytes ?? 5 * 1024 ** 3,
    lastLogin: raw.last_login_at ?? raw.created_at,
    createdAt: raw.created_at,
    department: raw.metadata?.department ?? "",
    documentsCount: raw.metadata?.documents_count ?? 0,
  };
}

export type User = ReturnType<typeof mapUser>;

export interface Summary {
  users?: {
    total?: number;
    active?: number;
    suspended?: number;
    by_role?: Record<string, number>;
  };
  storage?: { total_used_bytes?: number; by_tier?: Record<string, number> };
  audit?: { total_events?: number; top_actions?: Record<string, number> };
}

export function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 4) return `${(bytes / 1024 ** 4).toFixed(1)} TB`;
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
  if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${bytes} B`;
}

export function mapDashboardStats(res: Summary) {
  return {
    totalUsers: res.users?.total ?? 0,
    activeDocuments: 0,
    storageUsed: formatBytes(res.storage?.total_used_bytes ?? 0),
    activeSessions: res.users?.active ?? 0,
    usersGrowth: 0,
    documentsGrowth: 0,
    storageGrowth: 0,
    sessionsGrowth: 0,
  };
}

export function mapAnalyticsReport(res: Summary) {
  const points = (
    values: Record<string, number> | undefined,
    label: string,
    value: number
  ) =>
    Object.keys(values ?? {}).length
      ? Object.entries(values!).map(([label, value]) => ({ label, value }))
      : [{ label, value }];
  return {
    userSignups: points(res.users?.by_role, "Users", res.users?.total ?? 0),
    storageUsage: points(
      res.storage?.by_tier,
      "Used",
      res.storage?.total_used_bytes ?? 0
    ),
    documentActivity: points(
      res.audit?.top_actions,
      "Events",
      res.audit?.total_events ?? 0
    ),
    activeUsers: [
      { label: "Active", value: res.users?.active ?? 0 },
      { label: "Suspended", value: res.users?.suspended ?? 0 },
    ],
    topFileTypes: [],
    peakHours: [],
  };
}

export const getSummary = async () =>
  (await adminApi.get<Summary>("/admin/metrics/summary")).data;

export const getUsers = async () =>
  (
    (await adminApi.get<{ users?: RawUser[] }>("/admin/users")).data.users ?? []
  ).map(mapUser);

export const statsChanged = new EventTarget();
