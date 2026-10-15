import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { MatSnackBar } from '@angular/material/snack-bar';
import { MatDialog } from '@angular/material/dialog';
import { Router } from '@angular/router';
import { of } from 'rxjs';
import { UsersComponent } from '../pages/users/users.component';
import { QuotasComponent } from '../pages/quotas/quotas.component';
import { AuditComponent } from '../pages/audit/audit.component';
import { FeaturesComponent } from '../pages/features/features.component';
import { rawAuditLogs, rawFeatures, rawUsersPage } from './admin-fixtures';

function setup<T>(component: new (...args: any[]) => T) {
  TestBed.configureTestingModule({
    imports: [component, HttpClientTestingModule, RouterTestingModule, NoopAnimationsModule],
  });
  const fixture = TestBed.createComponent(component);
  const http = TestBed.inject(HttpTestingController);
  return { fixture, http, el: fixture.nativeElement as HTMLElement };
}

const keyup = (value: string) => ({ target: { value } }) as unknown as Event;

describe('UsersComponent (admin QA, HTTP-backed)', () => {
  let ctx: ReturnType<typeof setup<UsersComponent>>;
  let component: UsersComponent;

  beforeEach(() => {
    ctx = setup(UsersComponent);
    component = ctx.fixture.componentInstance;
    ctx.fixture.detectChanges();
    ctx.http.expectOne('/api/v1/admin/users').flush(rawUsersPage());
    ctx.fixture.detectChanges();
  });

  afterEach(() => ctx.http.verify());

  it('renders a row per user once loaded', () => {
    expect(component.loading).toBeFalse();
    expect(component.dataSource.data.length).toBe(3);
    expect(ctx.el.textContent).toContain('Alice Otter');
    expect(ctx.el.textContent).toContain('bob@otterworks.dev');
  });

  it('searches by name and by email, case-insensitively', () => {
    component.applyFilter(keyup('  ALICE '));
    expect(component.dataSource.filteredData.map(u => u.id)).toEqual(['u-1']);
    component.applyFilter(keyup('bob@'));
    expect(component.dataSource.filteredData.map(u => u.id)).toEqual(['u-2']);
    component.applyFilter(keyup(''));
    expect(component.dataSource.filteredData.length).toBe(3);
  });

  it('filters by role and status together', () => {
    component.roleFilter = 'viewer';
    component.statusFilter = 'suspended';
    component.applyFilters();
    expect(component.dataSource.filteredData.map(u => u.id)).toEqual(['u-2']);
    component.statusFilter = 'active';
    component.applyFilters();
    expect(component.dataSource.filteredData).toEqual([]);
  });

  it('suspends after confirmation and reloads the list', () => {
    const dialog = ctx.fixture.debugElement.injector.get(MatDialog);
    spyOn(dialog, 'open').and.returnValue({ afterClosed: () => of(true) } as any);
    const snack = spyOn(ctx.fixture.debugElement.injector.get(MatSnackBar), 'open');
    component.suspendUser(component.dataSource.data[0]);
    const req = ctx.http.expectOne('/api/v1/admin/users/u-1/suspend');
    expect(req.request.method).toBe('PUT');
    req.flush({ id: 'u-1', status: 'suspended' });
    expect(snack).toHaveBeenCalledWith('Alice Otter has been suspended', 'Dismiss', jasmine.any(Object));
    ctx.http.expectOne('/api/v1/admin/users').flush(rawUsersPage());
  });

  it('does not suspend when the dialog is cancelled', () => {
    spyOn(ctx.fixture.debugElement.injector.get(MatDialog), 'open').and.returnValue({ afterClosed: () => of(false) } as any);
    component.suspendUser(component.dataSource.data[0]);
    ctx.http.expectNone('/api/v1/admin/users/u-1/suspend');
  });

  it('restores a suspended user without a dialog', () => {
    component.restoreUser(component.dataSource.data[1]);
    ctx.http.expectOne({ method: 'PUT', url: '/api/v1/admin/users/u-2/activate' }).flush({ id: 'u-2', status: 'active' });
    ctx.http.expectOne('/api/v1/admin/users').flush(rawUsersPage());
  });

  it('navigates to the user detail page', () => {
    const nav = spyOn(ctx.fixture.debugElement.injector.get(Router), 'navigate');
    component.viewUser(component.dataSource.data[2]);
    expect(nav).toHaveBeenCalledWith(['/users', 'u-3']);
  });
});

describe('QuotasComponent (admin QA)', () => {
  let ctx: ReturnType<typeof setup<QuotasComponent>>;
  let component: QuotasComponent;

  beforeEach(() => {
    ctx = setup(QuotasComponent);
    component = ctx.fixture.componentInstance;
    ctx.fixture.detectChanges();
    ctx.http.expectOne('/api/v1/admin/users').flush(rawUsersPage());
    ctx.fixture.detectChanges();
  });

  afterEach(() => ctx.http.verify());

  it('renders the Storage Quotas page with users', () => {
    expect(ctx.el.querySelector('.page-title')?.textContent).toContain('Storage Quotas');
    expect(component.dataSource.data.length).toBe(3);
  });

  it('computes usage percent and guards zero quotas', () => {
    expect(component.getUsagePercent(component.dataSource.data[0])).toBeCloseTo(20, 5);
    expect(component.getUsagePercent({ ...component.dataSource.data[0], storageQuota: 0 })).toBe(0);
  });

  it('formats bytes', () => {
    expect(component.formatBytes(0)).toBe('0 B');
    expect(component.formatBytes(1536)).toBe('1.5 KB');
    expect(component.formatBytes(5 * 1024 ** 3)).toBe('5 GB');
  });

  it('updates a quota and confirms with a snackbar', () => {
    const snack = spyOn(ctx.fixture.debugElement.injector.get(MatSnackBar), 'open');
    component.updateQuota(component.dataSource.data[0], 50 * 1024 ** 3);
    const req = ctx.http.expectOne('/api/v1/admin/quotas/u-1');
    expect(req.request.body).toEqual({ quota: { quota_bytes: 50 * 1024 ** 3 } });
    req.flush({ quota_bytes: 50 * 1024 ** 3, used_bytes: 0 });
    expect(snack).toHaveBeenCalledWith('Quota updated for Alice Otter', 'Dismiss', jasmine.any(Object));
  });

  it('filters by search text', () => {
    component.applyFilter(keyup('Carol'));
    expect(component.dataSource.filteredData.map(u => u.id)).toEqual(['u-3']);
  });
});

describe('AuditComponent (admin QA)', () => {
  let ctx: ReturnType<typeof setup<AuditComponent>>;
  let component: AuditComponent;

  beforeEach(() => {
    ctx = setup(AuditComponent);
    component = ctx.fixture.componentInstance;
    ctx.fixture.detectChanges();
    ctx.http.expectOne('/api/v1/admin/audit-logs').flush(rawAuditLogs());
    ctx.fixture.detectChanges();
  });

  afterEach(() => ctx.http.verify());

  it('renders the Audit Logs page with events', () => {
    expect(ctx.el.querySelector('.page-title')?.textContent).toContain('Audit Logs');
    expect(component.dataSource.data.length).toBe(3);
  });

  it('searches across user, action, resource and details', () => {
    component.applyFilter(keyup('abuse'));
    expect(component.dataSource.filteredData.map(e => e.id)).toEqual(['a-1']);
    component.applyFilter(keyup('f-1'));
    expect(component.dataSource.filteredData.map(e => e.id)).toEqual(['a-2']);
  });

  it('filters by action and severity', () => {
    component.actionFilter = 'update';
    component.severityFilter = 'warning';
    component.applyFilters();
    expect(component.dataSource.filteredData.map(e => e.id)).toEqual(['a-3']);
  });
});

describe('FeaturesComponent (admin QA)', () => {
  let ctx: ReturnType<typeof setup<FeaturesComponent>>;
  let component: FeaturesComponent;

  beforeEach(() => {
    ctx = setup(FeaturesComponent);
    component = ctx.fixture.componentInstance;
    ctx.fixture.detectChanges();
    ctx.http.expectOne('/api/v1/admin/features').flush(rawFeatures());
    ctx.fixture.detectChanges();
  });

  afterEach(() => ctx.http.verify());

  it('renders one toggle per flag', () => {
    expect(component.loading).toBeFalse();
    expect(ctx.el.querySelectorAll('mat-slide-toggle').length).toBe(2);
  });

  it('filters by name, description and key', () => {
    component.searchTerm = 'semantic';
    expect(component.filteredFlags.map(f => f.id)).toEqual(['f-2']);
    component.searchTerm = 'real-time';
    expect(component.filteredFlags.map(f => f.id)).toEqual(['f-1']);
    component.searchTerm = '';
    expect(component.filteredFlags.length).toBe(2);
  });

  it('toggles a flag to the opposite state', () => {
    const snack = spyOn(ctx.fixture.debugElement.injector.get(MatSnackBar), 'open');
    component.toggleFlag(component.flags[1]);
    const req = ctx.http.expectOne('/api/v1/admin/features/f-2');
    expect(req.request.body).toEqual({ feature: { enabled: true } });
    req.flush({});
    expect(snack).toHaveBeenCalledWith('beta_search enabled', 'Dismiss', jasmine.any(Object));
  });

  it('toggling the same flag twice sends opposite states [REAL: toggleFlag never updates flag.enabled]', () => {
    const flag = component.flags[1];
    component.toggleFlag(flag);
    ctx.http.expectOne('/api/v1/admin/features/f-2').flush({});
    component.toggleFlag(flag);
    const second = ctx.http.expectOne('/api/v1/admin/features/f-2');
    expect(second.request.body).toEqual({ feature: { enabled: false } });
    second.flush({});
  });
});
