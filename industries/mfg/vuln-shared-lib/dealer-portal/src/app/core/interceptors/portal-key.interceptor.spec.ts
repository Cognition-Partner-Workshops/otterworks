import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Router, provideRouter } from '@angular/router';
import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';
import { portalKeyInterceptor } from './portal-key.interceptor';

describe('portalKeyInterceptor', () => {
  let client: HttpClient;
  let http: HttpTestingController;
  let auth: AuthService;
  let router: Router;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        provideRouter([]),
        provideHttpClient(withInterceptors([portalKeyInterceptor])),
        provideHttpClientTesting(),
      ],
    });
    client = TestBed.inject(HttpClient);
    http = TestBed.inject(HttpTestingController);
    auth = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  afterEach(() => http.verify());

  it('has no browser API key configuration', () => {
    expect(Object.keys(environment).filter(key => /key/i.test(key))).toEqual([]);
    expect('portalApiKey' in environment).toBeFalse();
  });

  it('sends credentials without a portal key to BFF calls', () => {
    client.get('/bff/inventory').subscribe();
    const req = http.expectOne('/bff/inventory');
    expect(req.request.headers.has('X-Portal-Key')).toBeFalse();
    expect(req.request.withCredentials).toBeTrue();
    req.flush([]);
  });

  it('leaves other requests untouched', () => {
    client.get('/assets/config.json').subscribe();
    const req = http.expectOne('/assets/config.json');
    expect(req.request.headers.has('X-Portal-Key')).toBeFalse();
    expect(req.request.withCredentials).toBeFalse();
    req.flush({});
  });

  it('sends the user back to sign-in when the BFF session has expired', () => {
    spyOn(auth, 'clear');
    spyOn(router, 'navigate');
    client.get('/bff/claims').subscribe({ error: () => undefined });
    http.expectOne('/bff/claims').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.clear).toHaveBeenCalled();
    expect(router.navigate).toHaveBeenCalledWith(['/sign-in'], jasmine.any(Object));
  });

  it('does not redirect on a failed sign-in', () => {
    spyOn(router, 'navigate');
    client.post('/bff/session', {}).subscribe({ error: () => undefined });
    http.expectOne('/bff/session').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(router.navigate).not.toHaveBeenCalled();
  });
});
