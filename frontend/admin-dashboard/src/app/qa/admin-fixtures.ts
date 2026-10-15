export const rawUser = (overrides: Record<string, unknown> = {}) => ({
  id: 'u-1',
  email: 'alice@otterworks.dev',
  display_name: 'Alice Otter',
  role: 'editor',
  status: 'active',
  avatar_url: null,
  last_login_at: '2026-10-01T10:00:00Z',
  created_at: '2026-01-01T00:00:00Z',
  metadata: { department: 'Engineering', documents_count: 12 },
  storage_quota: { user_id: 'u-1', quota_bytes: 10 * 1024 ** 3, used_bytes: 2 * 1024 ** 3 },
  ...overrides,
});

export const rawUsersPage = () => ({
  users: [
    rawUser(),
    rawUser({ id: 'u-2', email: 'bob@otterworks.dev', display_name: 'Bob Beaver', role: 'viewer', status: 'suspended', storage_quota: null }),
    rawUser({ id: 'u-3', email: 'carol@otterworks.dev', display_name: 'Carol Admin', role: 'admin' }),
  ],
  total: 3,
  page: 1,
  per_page: 25,
});

export const rawAuditLogs = () => ({
  audit_logs: [
    { id: 'a-1', action: 'user.suspended', actor_id: 'admin-1', actor_email: 'admin@otterworks.dev', resource_type: 'AdminUser', resource_id: 'u-2', changes_made: { reason: 'abuse' }, ip_address: '10.0.0.1', created_at: '2026-10-02T00:00:00Z' },
    { id: 'a-2', action: 'feature_flag.updated', actor_id: 'admin-1', actor_email: null, resource_type: 'FeatureFlag', resource_id: 'f-1', changes_made: null, ip_address: null, created_at: '2026-10-01T00:00:00Z' },
    { id: 'a-3', action: 'system_config.updated', actor_id: null, actor_email: null, resource_type: 'SystemConfig', resource_id: null, changes_made: null, ip_address: null, created_at: '2026-09-30T00:00:00Z' },
  ],
  total: 3,
});

export const rawFeatures = () => ({
  features: [
    { id: 'f-1', name: 'Real Time Collab', description: 'Live cursors', enabled: true, metadata: { category: 'Collaboration', updated_by: 'ops' }, updated_at: '2026-10-01T00:00:00Z' },
    { id: 'f-2', name: 'beta_search', description: 'Semantic search', enabled: false, metadata: {}, updated_at: '2026-10-01T00:00:00Z' },
  ],
});

export const rawHealth = () => ({
  status: 'degraded',
  timestamp: '2026-10-15T00:00:00Z',
  services: [
    { name: 'auth-service', status: 'healthy', latency_ms: 4 },
    { name: 'search-service', status: 'unhealthy', latency_ms: 0, message: 'Connection refused' },
    { name: 'mystery-service', status: 'unknown' },
  ],
  database: { status: 'healthy', latency_ms: 1 },
  redis: { status: 'unhealthy', message: 'timeout' },
});

export const rawMetricsSummary = () => ({
  users: { total: 42, active: 40, suspended: 2, by_role: { admin: 2, viewer: 40 } },
  storage: { total_used_bytes: 3 * 1024 ** 3, users_over_quota: 1, by_tier: { free: 41, pro: 1 } },
  features: { total: 5, enabled: 3 },
  audit: { total_events: 9, top_actions: { 'user.suspended': 4 } },
});
