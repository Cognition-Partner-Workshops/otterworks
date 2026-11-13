import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { PortalApiService } from './portal-api.service';

describe('PortalApiService', () => {
  let api: PortalApiService;
  let http: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    api = TestBed.inject(PortalApiService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => http.verify());

  it('loads the dealer inventory', () => {
    api.inventory().subscribe(list => expect(list.length).toBe(1));
    const req = http.expectOne('/bff/inventory');
    expect(req.request.method).toBe('GET');
    req.flush([{ vin: '1VSLA0000AA000001', model: 'Ranger LT', year: 2026, status: 'AVAILABLE', priceCents: 1, imageUrl: '' }]);
  });

  it('encodes the VIN when loading a single vehicle', () => {
    api.vehicle('1VSL A/1').subscribe(v => expect(v.vin).toBe('1VSL A/1'));
    http.expectOne('/bff/inventory/1VSL%20A%2F1').flush({ vin: '1VSL A/1' });
  });

  it('loads warranty claims', () => {
    api.claims().subscribe(list => expect(list).toEqual([]));
    http.expectOne('/bff/claims').flush([]);
  });

  it('submits a warranty claim', () => {
    api.submitClaim({ vin: '1VSLA0000AA000001', description: 'Door seal leaks' }).subscribe(c => expect(c.id).toBe('WC-9'));
    const req = http.expectOne('/bff/claims');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ vin: '1VSLA0000AA000001', description: 'Door seal leaks' });
    req.flush({ id: 'WC-9' }, { status: 201, statusText: 'Created' });
  });

  it('loads dealer notices', () => {
    api.notices().subscribe(list => expect(list.length).toBe(0));
    http.expectOne('/bff/notices').flush([]);
  });
});
