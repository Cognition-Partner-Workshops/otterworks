import { describe, expect, it } from 'vitest';
import { formatBytes, mapAnalyticsReport, mapDashboardStats, mapUser } from './api';

describe('admin raw backend mappers', () => {
  const user = { id: 'u1', email: 'user@example.test', display_name: 'Test User', role: 'editor', status: 'active', created_at: '2025-11-01T09:00:00Z' };
  it('maps raw user fields and nested metadata without generic key conversion', () => {
    expect(mapUser({ ...user, last_login_at: '2026-01-01T10:00:00Z', avatar_url: '/avatar', storage_quota: { used_bytes: 123, quota_bytes: 456 }, metadata: { department: 'Finance', documents_count: 7 } })).toEqual({
      id: 'u1', email: user.email, displayName: 'Test User', role: 'editor', status: 'active', avatarUrl: '/avatar', storageUsed: 123, storageQuota: 456, lastLogin: '2026-01-01T10:00:00Z', createdAt: user.created_at, department: 'Finance', documentsCount: 7,
    });
  });
  it('defaults missing user fields and uses created date for null last login', () => {
    expect(mapUser({ ...user, last_login_at: null })).toMatchObject({ storageUsed: 0, storageQuota: 5 * 1024 ** 3, lastLogin: user.created_at, department: '', documentsCount: 0 });
    expect(mapUser(user).lastLogin).toBe(user.created_at);
    expect(mapUser({ ...user, last_login_at: '' }).lastLogin).toBe('');
    expect(mapUser({ ...user, storage_quota: { used_bytes: 0, quota_bytes: 0 } }).storageQuota).toBe(0);
  });
  it('maps dashboard quirks rather than inventing documents, sessions or growth', () => {
    expect(mapDashboardStats({ users: { total: 14, active: 8 }, storage: { total_used_bytes: 105 * 64 * 1024 ** 2 } })).toEqual({ totalUsers: 14, activeDocuments: 0, storageUsed: '6.6 GB', activeSessions: 8, usersGrowth: 0, documentsGrowth: 0, storageGrowth: 0, sessionsGrowth: 0 });
    expect(mapDashboardStats({})).toEqual({ totalUsers: 0, activeDocuments: 0, storageUsed: '0 B', activeSessions: 0, usersGrowth: 0, documentsGrowth: 0, storageGrowth: 0, sessionsGrowth: 0 });
  });
  it('derives charts from role counts and audit actions in backend insertion order', () => {
    expect(mapAnalyticsReport({ users: { by_role: { editor: 5, admin: 3 } }, storage: { by_tier: { standard: 10 } }, audit: { top_actions: { 'user.login': 14 } } })).toMatchObject({
      userSignups: [{ label: 'editor', value: 5 }, { label: 'admin', value: 3 }], storageUsage: [{ label: 'standard', value: 10 }], documentActivity: [{ label: 'user.login', value: 14 }], topFileTypes: [], peakHours: [],
    });
  });
  it('uses total fallbacks for absent or empty chart breakdowns', () => {
    expect(mapAnalyticsReport({ users: { total: 14, active: 8, suspended: 3, by_role: {} }, storage: { total_used_bytes: 123, by_tier: {} }, audit: { total_events: 17, top_actions: {} } })).toMatchObject({
      userSignups: [{ label: 'Users', value: 14 }], storageUsage: [{ label: 'Used', value: 123 }], documentActivity: [{ label: 'Events', value: 17 }], activeUsers: [{ label: 'Active', value: 8 }, { label: 'Suspended', value: 3 }],
    });
    expect(mapAnalyticsReport({}).userSignups).toEqual([{ label: 'Users', value: 0 }]);
    expect(mapAnalyticsReport({}).documentActivity).toEqual([{ label: 'Events', value: 0 }]);
  });
  it.each([[0, '0 B'], [1023, '1023 B'], [1024, '1.0 KB'], [1536, '1.5 KB'], [1024 ** 2, '1.0 MB'], [1024 ** 3, '1.0 GB'], [1024 ** 4, '1.0 TB']])('formats %s bytes as %s', (bytes, expected) => {
    expect(formatBytes(bytes as number)).toBe(expected);
  });
});
