import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { OdlParityApiService } from './odl-parity-api.service';

describe('OdlParityApiService', () => {
  let service: OdlParityApiService;
  let http: HttpTestingController;
  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(OdlParityApiService);
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => http.verify());

  it('resolves latest summary to the full report and encodes run IDs', () => {
    service.getReport('latest').subscribe();
    http.expectOne('/api/v1/odl/parity/latest').flush({ run_id: 'run 1' });
    http.expectOne('/api/v1/odl/parity/run%201').flush({ run_id: 'run 1' });
  });

  it('lists runs and requests CSV through HttpClient as a blob', () => {
    service.listRuns().subscribe();
    http.expectOne('/api/v1/odl/parity').flush({ items: [] });
    service.getReportFile('run 1').subscribe();
    const request = http.expectOne('/api/v1/odl/parity/run%201.csv');
    expect(request.request.responseType).toBe('blob');
    request.flush(new Blob(['csv']));
  });

  it('bounds and encodes exception pages', () => {
    service.listExceptions('transform_failed', 'exc 1').subscribe();
    const request = http.expectOne(r => r.url === '/api/v1/odl/exceptions');
    expect(request.request.params.get('limit')).toBe('20');
    expect(request.request.params.get('reason')).toBe('transform_failed');
    expect(request.request.params.get('cursor')).toBe('exc 1');
    request.flush({ items: [], next_cursor: null });
  });
});
