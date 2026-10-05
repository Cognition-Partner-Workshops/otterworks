export interface DashboardStats {
  totalUsers: number;
  activeDocuments: number;
  storageUsed: string;
  activeSessions: number;
  usersGrowth: number;
  documentsGrowth: number;
  storageGrowth: number;
  sessionsGrowth: number;
}

export interface StorageUsage {
  totalBytes: number;
  fileCount: number;
  storageUsed: string;
  byUser: Record<string, { fileCount: number; totalBytes: number }>;
}

export interface ChartDataPoint {
  label: string;
  value: number;
}

export interface AnalyticsReport {
  userSignups: ChartDataPoint[];
  storageUsage: ChartDataPoint[];
  documentActivity: ChartDataPoint[];
  activeUsers: ChartDataPoint[];
  topFileTypes: ChartDataPoint[];
  peakHours: ChartDataPoint[];
}
