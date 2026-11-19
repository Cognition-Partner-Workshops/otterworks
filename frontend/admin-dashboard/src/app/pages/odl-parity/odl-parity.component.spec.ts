import { ComponentFixture, TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { OdlParityComponent } from './odl-parity.component';
import { ParityReport } from '../../core/models/odl-parity.model';

const REPORT: ParityReport = {
  run_id: 'run-1', generated_at: '2026-11-19T22:00:00Z', passed: false,
  exception_summary: { candidate_match_unconfirmed: 600 },
  tables: { 'ODL.CUSTMAST': { source: 'db2', depths: {
    count: { source: 50000, placed: 50000, unplaced: 0, passed: true },
    profile: { fields: { name: { min: { source: 'a', target: 'b', passed: false } }, key: { null: { source: 0, target: 0, passed: true } } }, passed: false },
    keyed_hash: { matched: 49999, mismatched: 1, missing_in_target: 0, extra_in_target: 0, passed: false },
    sampled_values: { size: 490, fields_compared: 3430, difference_count: 1, passed: false },
  } } },
};

describe('OdlParityComponent', () => {
  let fixture: ComponentFixture<OdlParityComponent>;
  let component: OdlParityComponent;
  let http: HttpTestingController;
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [OdlParityComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();
    fixture = TestBed.createComponent(OdlParityComponent);
    component = fixture.componentInstance;
    http = TestBed.inject(HttpTestingController);
    fixture.detectChanges();
    http.expectOne('/api/v1/odl/parity').flush({ items: [{ run_id: REPORT.run_id, passed: REPORT.passed }] });
  });
  afterEach(() => { fixture.destroy(); http.verify(); });

  function loadReport(): void {
    http.expectOne('/api/v1/odl/parity/latest').flush({ run_id: REPORT.run_id });
    http.expectOne('/api/v1/odl/parity/run-1').flush(REPORT);
    http.expectOne(r => r.url === '/api/v1/odl/exceptions').flush({ items: [], next_cursor: null });
    fixture.detectChanges();
  }

  it('renders all four depths, profile failures and the exception summary', () => {
    loadReport();
    expect(component.rows[0].profileChecked).toBe(2);
    expect(component.rows[0].profileFailed).toBe(1);
    const text = (fixture.nativeElement as HTMLElement).textContent!;
    for (const label of ['FAIL', 'ODL.CUSTMAST', 'Fields failed 1', '49,999', '3,430', 'candidate_match_unconfirmed', '600', 'No exceptions found.']) {
      expect(text).toContain(label);
    }
  });

  it('pages and filters live exceptions', () => {
    loadReport();
    component.resetExceptions();
    http.expectOne(r => r.url === '/api/v1/odl/exceptions').flush({ items: [{ _id: 'e1', reason: 'candidate_match_unconfirmed', status: 'open', source_keys: ['db2:C0000003'] }], next_cursor: 'e1' });
    component.nextExceptions();
    http.expectOne(r => r.params.get('cursor') === 'e1').flush({ items: [], next_cursor: null });
    expect(component.previousCursors.length).toBe(1);
    component.previousExceptions();
    http.expectOne(r => r.url === '/api/v1/odl/exceptions' && !r.params.has('cursor')).flush({ items: [], next_cursor: null });
    component.reasonFilter = 'candidate_match_unconfirmed';
    component.resetExceptions();
    http.expectOne(r => r.params.get('reason') === 'candidate_match_unconfirmed').flush({ items: [], next_cursor: null });
    expect(component.previousCursors.length).toBe(0);
  });

  it('cancels stale report requests and supports empty reports', () => {
    const pending = http.expectOne('/api/v1/odl/parity/latest');
    component.runIdInput = 'empty';
    component.loadRun();
    expect(pending.cancelled).toBeTrue();
    http.expectOne('/api/v1/odl/parity/empty').flush({ ...REPORT, run_id: 'empty', passed: true, tables: {}, exception_summary: {} });
    http.expectOne(r => r.url === '/api/v1/odl/exceptions').flush({ items: [], next_cursor: null });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No table results');
    expect(fixture.nativeElement.textContent).toContain('No exceptions recorded');
  });

  it('shows missing-report and retryable request errors', () => {
    http.expectOne('/api/v1/odl/parity/latest').flush({}, { status: 404, statusText: 'Not Found' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('No parity report found');
    component.loadRun();
    http.expectOne('/api/v1/odl/parity/latest').flush({}, { status: 503, statusText: 'Unavailable' });
    expect(component.loading).toBeFalse();
    expect(component.error).toContain('503');
  });

  it('downloads an authenticated CSV blob and reports failures', () => {
    loadReport();
    spyOn(URL, 'createObjectURL').and.returnValue('blob:csv');
    const click = spyOn(HTMLAnchorElement.prototype, 'click');
    component.downloadCsv();
    const request = http.expectOne('/api/v1/odl/parity/run-1.csv');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['csv']));
    expect(click).toHaveBeenCalled();
    component.downloadCsv();
    http.expectOne('/api/v1/odl/parity/run-1.csv').flush(new Blob(), { status: 500, statusText: 'Error' });
    expect(component.error).toContain('CSV download failed');
  });

  it('shows exception request errors without hiding the report', () => {
    loadReport();
    component.resetExceptions();
    http.expectOne(r => r.url === '/api/v1/odl/exceptions').flush({}, { status: 503, statusText: 'Unavailable' });
    expect(component.report).not.toBeNull();
    expect(component.exceptionsError).toContain('Could not load exceptions');
    expect(component.exceptionsLoading).toBeFalse();
  });
});
