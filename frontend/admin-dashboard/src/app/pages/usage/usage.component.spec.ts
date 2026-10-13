import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { UsageComponent } from './usage.component';

describe('UsageComponent', () => {
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [UsageComponent, HttpClientTestingModule, NoopAnimationsModule],
    });
    http = TestBed.inject(HttpTestingController);
  });

  it('reads the tenant usage and plan seat reports for the business date and shows the backend', () => {
    const fixture = TestBed.createComponent(UsageComponent);
    fixture.detectChanges();
    const report = (name: string, source: string, rows: any[]) => ({
      report: name, backend: 'snowflake', source, parameters: {}, fields: [], rowCount: rows.length, rows,
    });
    http.expectOne(r => r.url === '/api/v1/reports/ubw/rpt_tenant_usage_daily' && r.params.get('businessDate') === '2026-09-30')
      .flush(report('rpt_tenant_usage_daily', 'REPORTS.RPT_TENANT_USAGE_DAILY', [
        { tenant_name: 'A', api_units: 2, compute_units: 3, storage_peak_mb: 10 },
        { tenant_name: 'B', api_units: 5, compute_units: 1, storage_peak_mb: 30 },
      ]));
    http.expectOne(r => r.url === '/api/v1/reports/ubw/rpt_plan_mix')
      .flush(report('rpt_plan_mix', 'REPORTS.RPT_PLAN_MIX', [{ plan_tier: 'growth', seat_count: 7 }]));
    fixture.detectChanges();
    const component = fixture.componentInstance;
    expect(component.sum(component.usage!.rows, 'api_units')).toBe(7);
    expect(component.topTenants()[0]['tenant_name']).toBe('B');
    expect(fixture.nativeElement.querySelector('[data-testid="ubw-backend"]').textContent).toContain('Snowflake');
    http.verify();
  });
});
