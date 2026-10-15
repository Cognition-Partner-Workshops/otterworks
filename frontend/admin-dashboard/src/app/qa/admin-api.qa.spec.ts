import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AdminApiService } from '../core/services/admin-api.service';
import { rawAuditLogs, rawFeatures, rawHealth, rawMetricsSummary, rawUser, rawUsersPage } from './admin-fixtures';

describe('AdminApiService (admin QA, HTTP contract)', () => {
  let service: AdminApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(AdminApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  describe('users', () => {
    it('GETs /api/v1/admin/users and maps snake_case fields', () => {
      let users: any[] = [];
      service.getUsers().subscribe(u => (users = u));
      const req = http.expectOne('/api/v1/admin/users');
      expect(req.request.method).toBe('GET');
      req.flush(rawUsersPage());

      expect(users.length).toBe(3);
      expect(users[0]).toEqual(jasmine.objectContaining({
        id: 'u-1', email: 'alice@otterworks.dev', displayName: 'Alice Otter', role: 'editor', status: 'active',
        storageUsed: 2 * 1024 ** 3, storageQuota: 10 * 1024 ** 3, department: 'Engineering', documentsCount: 12,
        lastLogin: '2026-10-01T10:00:00Z',
      }));
    });

    it('defaults storage to 0 used / 5 GB quota when a user has no quota row', () => {
      let users: any[] = [];
      service.getUsers().subscribe(u => (users = u));
      http.expectOne('/api/v1/admin/users').flush(rawUsersPage());
      expect(users[1].storageUsed).toBe(0);
      expect(users[1].storageQuota).toBe(5 * 1024 ** 3);
    });

    it('falls back to created_at when last_login_at is missing', () => {
      let user: any;
      service.getUser('u-1').subscribe(u => (user = u));
      http.expectOne('/api/v1/admin/users/u-1').flush(rawUser({ last_login_at: null }));
      expect(user.lastLogin).toBe('2026-01-01T00:00:00Z');
    });

    it('returns an empty list when the response has no users key', () => {
      let users: any[] | undefined;
      service.getUsers().subscribe(u => (users = u));
      http.expectOne('/api/v1/admin/users').flush({});
      expect(users).toEqual([]);
    });

    it('suspends via PUT /users/:id/suspend', () => {
      let user: any;
      service.suspendUser('u-1').subscribe(u => (user = u));
      const req = http.expectOne('/api/v1/admin/users/u-1/suspend');
      expect(req.request.method).toBe('PUT');
      req.flush(rawUser({ status: 'suspended' }));
      expect(user.status).toBe('suspended');
    });

    it('restores via PUT /users/:id/activate', () => {
      let user: any;
      service.restoreUser('u-2').subscribe(u => (user = u));
      const req = http.expectOne('/api/v1/admin/users/u-2/activate');
      expect(req.request.method).toBe('PUT');
      req.flush(rawUser({ id: 'u-2', status: 'active' }));
      expect(user.status).toBe('active');
    });

    it('deletes via DELETE /users/:id', () => {
      service.deleteUser('u-3').subscribe();
      const req = http.expectOne('/api/v1/admin/users/u-3');
      expect(req.request.method).toBe('DELETE');
      req.flush(null);
    });

    it('loads user activity from audit-logs filtered by actor', () => {
      let activity: any[] = [];
      service.getUserActivity('admin-1').subscribe(a => (activity = a));
      http.expectOne('/api/v1/admin/audit-logs?actor_id=admin-1&per_page=20').flush(rawAuditLogs());
      expect(activity[0]).toEqual(jasmine.objectContaining({ userId: 'admin-1', action: 'user.suspended', resource: 'AdminUser u-2' }));
      expect(activity[0].details).toBe('{"reason":"abuse"}');
      expect(activity[2].resource).toBe('SystemConfig');
    });
  });

  describe('storage quotas', () => {
    it('PUTs { quota: { quota_bytes } } to /quotas/:userId', () => {
      let result: any;
      service.updateStorageQuota('u-1', 20 * 1024 ** 3).subscribe(r => (result = r));
      const req = http.expectOne('/api/v1/admin/quotas/u-1');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({ quota: { quota_bytes: 20 * 1024 ** 3 } });
      req.flush({ user_id: 'u-1', quota_bytes: 20 * 1024 ** 3, used_bytes: 123 });
      expect(result.storageQuota).toBe(20 * 1024 ** 3);
      expect(result.storageUsed).toBe(123);
    });

    it('falls back to the requested quota when the response omits quota_bytes', () => {
      let result: any;
      service.updateStorageQuota('u-1', 777).subscribe(r => (result = r));
      http.expectOne('/api/v1/admin/quotas/u-1').flush({});
      expect(result.storageQuota).toBe(777);
      expect(result.storageUsed).toBe(0);
    });
  });

  describe('audit logs', () => {
    it('maps backend actions to UI action + severity', () => {
      let events: any[] = [];
      service.getAuditEvents().subscribe(e => (events = e));
      http.expectOne('/api/v1/admin/audit-logs').flush(rawAuditLogs());
      expect(events.map(e => e.action)).toEqual(['suspend', 'update', 'update']);
      expect(events.map(e => e.severity)).toEqual(['warning', 'info', 'warning']);
      expect(events[0].userName).toBe('admin@otterworks.dev');
      expect(events[1].userName).toBe('admin-1');
      expect(events[2].userName).toBe('System');
      expect(events[1].details).toBe('feature_flag.updated');
    });

    const actionCases: [string, string][] = [
      ['announcement.created', 'create'], ['user.deleted', 'delete'], ['user.activated', 'restore'],
      ['user.restored', 'restore'], ['auth.login', 'login'], ['auth.logout', 'logout'],
      ['file.upload', 'upload'], ['file.download', 'download'], ['doc.share', 'share'], ['quota.updated', 'update'],
    ];
    actionCases.forEach(([backend, ui]) => {
      it(`normalises ${backend} -> ${ui}`, () => {
        let events: any[] = [];
        service.getAuditEvents().subscribe(e => (events = e));
        http.expectOne('/api/v1/admin/audit-logs').flush({ audit_logs: [{ id: 'x', action: backend, created_at: 'now' }] });
        expect(events[0].action).toBe(ui);
      });
    });
  });

  describe('feature flags', () => {
    it('maps key/category/updatedBy with defaults', () => {
      let flags: any[] = [];
      service.getFeatureFlags().subscribe(f => (flags = f));
      http.expectOne('/api/v1/admin/features').flush(rawFeatures());
      expect(flags[0]).toEqual(jasmine.objectContaining({ key: 'real-time-collab', category: 'Collaboration', updatedBy: 'ops', enabled: true }));
      expect(flags[1]).toEqual(jasmine.objectContaining({ key: 'beta_search', category: 'General', updatedBy: 'Admin', enabled: false }));
    });

    it('toggles via PUT { feature: { enabled } }', () => {
      service.toggleFeatureFlag('f-2', true).subscribe();
      const req = http.expectOne('/api/v1/admin/features/f-2');
      expect(req.request.method).toBe('PUT');
      expect(req.request.body).toEqual({ feature: { enabled: true } });
      req.flush({ ...rawFeatures().features[1], enabled: true });
    });
  });

  describe('system health', () => {
    it('maps service statuses and appends postgres/redis', () => {
      let services: any[] = [];
      service.getSystemHealth().subscribe(s => (services = s));
      http.expectOne('/api/v1/admin/health/services').flush(rawHealth());
      const byName = Object.fromEntries(services.map(s => [s.name, s]));
      expect(services.length).toBe(5);
      expect(byName['auth-service']).toEqual(jasmine.objectContaining({ status: 'healthy', port: 8081, responseTime: 4 }));
      expect(byName['search-service']).toEqual(jasmine.objectContaining({ status: 'down', details: 'Connection refused' }));
      expect(byName['mystery-service']).toEqual(jasmine.objectContaining({ status: 'degraded', version: 'unknown', port: 0 }));
      expect(byName['postgres'].status).toBe('healthy');
      expect(byName['redis']).toEqual(jasmine.objectContaining({ status: 'down', details: 'timeout', port: 6379 }));
    });
  });

  describe('dashboard', () => {
    it('maps the metrics summary to dashboard stats', () => {
      let stats: any;
      service.getDashboardStats().subscribe(s => (stats = s));
      http.expectOne('/api/v1/admin/metrics/summary').flush(rawMetricsSummary());
      expect(stats.totalUsers).toBe(42);
      expect(stats.activeSessions).toBe(40);
      expect(stats.storageUsed).toContain('GB');
    });

    it('survives an empty metrics summary', () => {
      let stats: any;
      service.getDashboardStats().subscribe(s => (stats = s));
      http.expectOne('/api/v1/admin/metrics/summary').flush({});
      expect(stats.totalUsers).toBe(0);
      expect(stats.activeSessions).toBe(0);
    });
  });

  describe('auto-investigate setting', () => {
    it('GETs and PUTs /settings/auto_investigate', () => {
      service.getAutoInvestigate().subscribe();
      http.expectOne({ method: 'GET', url: '/api/v1/admin/settings/auto_investigate' }).flush({ enabled: true });
      service.setAutoInvestigate(false).subscribe();
      const req = http.expectOne({ method: 'PUT', url: '/api/v1/admin/settings/auto_investigate' });
      expect(req.request.body).toEqual({ enabled: false });
      req.flush({ enabled: false });
    });
  });
});
