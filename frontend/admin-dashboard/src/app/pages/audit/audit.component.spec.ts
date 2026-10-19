import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { AuditComponent } from './audit.component';

const rawLogs = [
  { id: '1', actor_email: 'alice@otterworks.test', action: 'feature_flag.created', resource_type: 'FeatureFlag',
    resource_id: 'flag-a', created_at: '2026-10-03T00:00:00Z' },
  { id: '2', actor_email: 'bob@otterworks.test', action: 'user.suspended', resource_type: 'AdminUser',
    resource_id: 'user-b', created_at: '2026-10-02T00:00:00Z' },
  { id: '3', actor_email: 'carol@otterworks.test', action: 'config.updated', resource_type: 'SystemConfig',
    resource_id: 'cfg-c', created_at: '2026-10-01T00:00:00Z' },
];

describe('AuditComponent', () => {
  let fixture: ComponentFixture<AuditComponent>;
  let component: AuditComponent;
  let http: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AuditComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();
    fixture = TestBed.createComponent(AuditComponent);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/admin/audit-logs').flush({ audit_logs: rawLogs });
    fixture.detectChanges();
  });

  afterEach(() => http.verify());

  const visibleIds = () => component.dataSource.filteredData.map(e => e.id);

  it('maps backend actions to UI action + severity', () => {
    const byId = Object.fromEntries(component.dataSource.data.map(e => [e.id, e]));
    expect(byId['1'].action).toBe('create');
    expect(byId['1'].severity).toBe('info');
    expect(byId['2'].action).toBe('suspend');
    expect(byId['2'].severity).toBe('warning');
    expect(byId['3'].severity).toBe('warning');
  });

  it('renders a row per audit event', () => {
    expect(fixture.nativeElement.querySelectorAll('tr.mat-mdc-row').length).toBe(3);
  });

  it('free-text search matches the user name', () => {
    component.applyFilter({ target: { value: '  BOB ' } } as unknown as Event);
    expect(visibleIds()).toEqual(['2']);
  });

  it('action filter narrows to one action', () => {
    component.actionFilter = 'create';
    component.applyFilters();
    expect(visibleIds()).toEqual(['1']);
  });

  it('severity filter combines with action filter', () => {
    component.severityFilter = 'warning';
    component.applyFilters();
    expect(visibleIds().sort()).toEqual(['2', '3']);
    component.actionFilter = 'suspend';
    component.applyFilters();
    expect(visibleIds()).toEqual(['2']);
  });

  it('clearing filters restores all rows', () => {
    component.actionFilter = 'create';
    component.applyFilters();
    component.actionFilter = '';
    component.applyFilters();
    expect(visibleIds().length).toBe(3);
  });
});
