import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AdminApiService } from './admin-api.service';

describe('QA AdminApiService (HTTP contract)', () => {
  let service: AdminApiService;
  let http: HttpTestingController;

  const rawUser = {
    id: 'u-1',
    email: 'quinn@otterworks.io',
    display_name: 'Quinn Archer',
    role: 'editor',
    status: 'active',
    avatar_url: null,
    metadata: { department: 'QA', documents_count: 7 },
    last_login_at: '2026-10-10T00:00:00Z',
    created_at: '2026-01-01T00:00:00Z',
    storage_quota: { used_bytes: 1024, quota_bytes: 2048 },
  };

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(AdminApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  describe('users', () => {
    it('GETs /api/v1/admin/users and maps snake_case to camelCase', () => {
      let result: any[] = [];
      service.getUsers().subscribe(u => (result = u));
      const req = http.expectOne('/api/v1/admin/users');
      expect(req.request.method).toBe('GET');
      req.flush({ users: [rawUser], total: 1 });
      expect(result.length).toBe(1);
      expect(result[0]).toEqual(jasmine.objectContaining({
        id: 'u-1', email: 'quinn@otterworks.io', displayName: 'Quinn Archer', role: 'editor', status: 'active',
        storageUsed: 1024, storageQuota: 2048, lastLogin: '2026-10-10T00:00:00Z', department: 'QA', documentsCount: 7,
      }));
    });

    it('returns an empty list when the payload has no users key', () => {
      let result: any[] | undefined;
      service.getUsers().subscribe(u => (result = u));
      http.expectOne('/api/v1/admin/users').flush({});
      expect(result).toEqual([]);
    });

    it('defaults quota to 5 GB, lastLogin to createdAt and documentsCount to 0', () => {
      let user: any;
      service.getUser('u-2').subscribe(u => (user = u));
      http.expectOne('/api/v1/admin/users/u-2').flush({ ...rawUser, id: 'u-2', storage_quota: null, last_login_at: null, metadata: {} });
      expect(user.storageUsed).toBe(0);
      expect(user.storageQuota).toBe(5 * 1024 * 1024 * 1024);
      expect(user.lastLogin).toBe('2026-01-01T00:00:00Z');
      expect(user.documentsCount).toBe(0);
      expect(user.department).toBe('');
    });

    it('PUTs suspend with an empty body', () => {
      let user: any;
      service.suspendUser('u-1').subscribe(u => (user = u));
      const req = http.expectOne('/api/v1/admin/users/u-1/suspend');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({});
      req.flush({ ...rawUser, status: 'suspended' });
      expect(user.status).toBe('suspended');
    });

    it('restores via PUT /activate', () => {
      service.restoreUser('u-1').subscribe();
      const req = http.expectOne('/api/v1/admin/users/u-1/activate');
      expect(req.request.method).toBe('PUT');
      req.flush(rawUser);
    });

    it('DELETEs a user', () => {
      service.deleteUser('u-1').subscribe();
      const req = http.expectOne('/api/v1/admin/users/u-1');
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });

    it('loads user activity from audit-logs filtered by actor', () => {
      let activity: any[] = [];
      service.getUserActivity('u-1').subscribe(a => (activity = a));
      const req = http.expectOne('/api/v1/admin/audit-logs?actor_id=u-1&per_page=20');
      req.flush({ audit_logs: [{ id: 'a1', actor_id: 'u-1', action: 'user.updated', resource_type: 'AdminUser', resource_id: 'u-9', created_at: 't', changes_made: { role: 'admin' }, ip_address: '1.2.3.4' }] });
      expect(activity[0]).toEqual(jasmine.objectContaining({ userId: 'u-1', resource: 'AdminUser u-9', details: '{"role":"admin"}', ipAddress: '1.2.3.4' }));
    });

    it('propagates HTTP errors to subscribers', () => {
      let status = 0;
      service.getUsers().subscribe({ error: e => (status = e.status) });
      http.expectOne('/api/v1/admin/users').flush({ error: 'boom' }, { status: 503, statusText: 'Unavailable' });
      expect(status).toBe(503);
    });
  });

  describe('metrics', () => {
    it('maps metrics summary into dashboard stats with formatted storage', () => {
      let stats: any;
      service.getDashboardStats().subscribe(s => (stats = s));
      http.expectOne('/api/v1/admin/metrics/summary').flush({
        users: { total: 10, active: 9 },
        storage: { total_used_bytes: 855772233724 },
      });
      expect(stats.totalUsers).toBe(10);
      expect(stats.activeSessions).toBe(9);
      expect(stats.storageUsed).toBe('797.0 GB');
    });

    const byteCases: [number, string][] = [
      [0, '0 B'], [512, '512 B'], [2048, '2.0 KB'], [5 * 1024 ** 2, '5.0 MB'], [3 * 1024 ** 4, '3.0 TB'],
    ];
    byteCases.forEach(([bytes, label]) => {
      it(`formats ${bytes} bytes as ${label}`, () => {
        let stats: any;
        service.getDashboardStats().subscribe(s => (stats = s));
        http.expectOne('/api/v1/admin/metrics/summary').flush({ storage: { total_used_bytes: bytes } });
        expect(stats.storageUsed).toBe(label);
      });
    });

    it('zeroes everything for an empty summary', () => {
      let stats: any;
      service.getDashboardStats().subscribe(s => (stats = s));
      http.expectOne('/api/v1/admin/metrics/summary').flush({});
      expect(stats.totalUsers).toBe(0);
      expect(stats.activeSessions).toBe(0);
      expect(stats.storageUsed).toBe('0 B');
    });

    it('builds an analytics report from role / tier / action breakdowns', () => {
      let report: any;
      service.getAnalyticsReport().subscribe(r => (report = r));
      http.expectOne('/api/v1/admin/metrics/summary').flush({
        users: { total: 3, active: 2, suspended: 1, by_role: { admin: 1, viewer: 2 } },
        storage: { by_tier: { pro: 3 } },
        audit: { top_actions: { 'user.suspended': 4 } },
      });
      expect(report.userSignups).toEqual([{ label: 'admin', value: 1 }, { label: 'viewer', value: 2 }]);
      expect(report.storageUsage).toEqual([{ label: 'pro', value: 3 }]);
      expect(report.documentActivity).toEqual([{ label: 'user.suspended', value: 4 }]);
      expect(report.activeUsers).toEqual([{ label: 'Active', value: 2 }, { label: 'Suspended', value: 1 }]);
    });

    it('falls back to totals when breakdowns are empty', () => {
      let report: any;
      service.getAnalyticsReport().subscribe(r => (report = r));
      http.expectOne('/api/v1/admin/metrics/summary').flush({ users: { total: 5 }, storage: { total_used_bytes: 9 }, audit: { total_events: 2 } });
      expect(report.userSignups).toEqual([{ label: 'Users', value: 5 }]);
      expect(report.storageUsage).toEqual([{ label: 'Used', value: 9 }]);
      expect(report.documentActivity).toEqual([{ label: 'Events', value: 2 }]);
    });
  });

  describe('audit logs', () => {
    const actionCases: [string, string, string][] = [
      ['user.created', 'create', 'info'],
      ['user.deleted', 'delete', 'warning'],
      ['user.suspended', 'suspend', 'warning'],
      ['user.activated', 'restore', 'info'],
      ['config.updated', 'update', 'warning'],
      ['bulk.users_updated', 'update', 'warning'],
      ['user.login', 'login', 'info'],
      ['file.download', 'download', 'info'],
      ['', 'update', 'info'],
    ];
    actionCases.forEach(([raw, action, severity]) => {
      it(`maps "${raw}" to action=${action} severity=${severity}`, () => {
        let events: any[] = [];
        service.getAuditEvents().subscribe(e => (events = e));
        http.expectOne('/api/v1/admin/audit-logs').flush({ audit_logs: [{ id: 'x', action: raw, created_at: 't' }] });
        expect(events[0].action).toBe(action);
        expect(events[0].severity).toBe(severity);
      });
    });

    it('uses actor_email as user name, falling back to actor_id then System', () => {
      let events: any[] = [];
      service.getAuditEvents().subscribe(e => (events = e));
      http.expectOne('/api/v1/admin/audit-logs').flush({ audit_logs: [
        { id: '1', action: 'user.updated', actor_email: 'a@x.io', actor_id: 'id-a' },
        { id: '2', action: 'user.updated', actor_id: 'id-b' },
        { id: '3', action: 'user.updated' },
      ] });
      expect(events.map(e => e.userName)).toEqual(['a@x.io', 'id-b', 'System']);
    });
  });

  describe('feature flags & announcements', () => {
    it('toggles a flag with a nested feature payload', () => {
      service.toggleFeatureFlag('f-1', false).subscribe();
      const req = http.expectOne('/api/v1/admin/features/f-1');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({ feature: { enabled: false } });
      req.flush({ id: 'f-1', name: 'Dark Mode', enabled: false });
    });

    it('derives a kebab-case key from the flag name', () => {
      let flags: any[] = [];
      service.getFeatureFlags().subscribe(f => (flags = f));
      http.expectOne('/api/v1/admin/features').flush({ features: [{ id: 'f', name: 'Dark Mode Beta', enabled: true }] });
      expect(flags[0].key).toBe('dark-mode-beta');
      expect(flags[0].category).toBe('General');
    });

    it('creates announcements as draft and maps priority to severity', () => {
      service.createAnnouncement({ title: 'T', content: 'B', priority: 'high', targetAudience: 'admins' } as any).subscribe();
      const req = http.expectOne('/api/v1/admin/announcements');
      expect(req.request.method).toBe('POST');
      expect(req.request.body).toEqual({ announcement: { title: 'T', body: 'B', severity: 'maintenance', status: 'draft', target_audience: { role: 'admins' } } });
      req.flush({ id: 'a', title: 'T', body: 'B', severity: 'maintenance', status: 'draft' });
    });

    it('maps announcement severity back to priority and sets publishedAt only when published', () => {
      let list: any[] = [];
      service.getAnnouncements().subscribe(a => (list = a));
      http.expectOne('/api/v1/admin/announcements').flush({ announcements: [
        { id: '1', severity: 'warning', status: 'published', starts_at: 's', updated_at: 'u' },
        { id: '2', severity: 'info', status: 'draft' },
      ] });
      expect(list[0].priority).toBe('medium');
      expect(list[0].publishedAt).toBe('s');
      expect(list[1].priority).toBe('low');
      expect(list[1].publishedAt).toBeUndefined();
      expect(list[1].targetAudience).toBe('all');
    });
  });

  describe('health', () => {
    it('maps service statuses and appends database/redis pseudo-services', () => {
      let services: any[] = [];
      service.getSystemHealth().subscribe(s => (services = s));
      http.expectOne('/api/v1/admin/health/services').flush({
        timestamp: 'ts',
        services: [
          { name: 'auth-service', status: 'healthy', latency_ms: 5 },
          { name: 'file-service', status: 'unhealthy' },
          { name: 'mystery', status: 'timeout' },
        ],
        database: { status: 'healthy' },
        redis: { status: 'down' },
      });
      expect(services.map(s => s.status)).toEqual(['healthy', 'down', 'degraded', 'healthy', 'down']);
      expect(services[0].port).toBe(8081);
      expect(services[2].version).toBe('unknown');
      expect(services.map(s => s.name)).toContain('postgres');
    });
  });

  describe('settings', () => {
    it('reads auto_investigate', () => {
      let value: any;
      service.getAutoInvestigate().subscribe(v => (value = v));
      http.expectOne('/api/v1/admin/settings/auto_investigate').flush({ enabled: false });
      expect(value).toEqual({ enabled: false });
    });

    it('writes auto_investigate with PUT {enabled}', () => {
      service.setAutoInvestigate(true).subscribe();
      const req = http.expectOne('/api/v1/admin/settings/auto_investigate');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({ enabled: true });
      req.flush({ enabled: true });
    });
  });

  describe('quotas', () => {
    it('PUTs quota_bytes and maps the response', () => {
      let user: any;
      service.updateStorageQuota('u-1', 4096).subscribe(u => (user = u));
      const req = http.expectOne('/api/v1/admin/quotas/u-1');
      expect(req.request.body).toEqual({ quota: { quota_bytes: 4096 } });
      req.flush({ used_bytes: 10, quota_bytes: 4096 });
      expect(user.storageQuota).toBe(4096);
      expect(user.storageUsed).toBe(10);
    });
  });
});
