import { TestBed } from '@angular/core/testing';
import { HTTP_INTERCEPTORS, HttpClient, HttpContext } from '@angular/common/http';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { JwtInterceptor } from './jwt.interceptor';
import { AuthService } from '../services/auth.service';
import { PEER_REQUEST } from '../services/migration-api.service';

describe('QA JwtInterceptor', () => {
  let http: HttpClient;
  let controller: HttpTestingController;
  let auth: jasmine.SpyObj<AuthService>;

  beforeEach(() => {
    auth = jasmine.createSpyObj('AuthService', ['getToken', 'logout']);
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: HTTP_INTERCEPTORS, useClass: JwtInterceptor, multi: true },
      ],
    });
    http = TestBed.inject(HttpClient);
    controller = TestBed.inject(HttpTestingController);
  });

  afterEach(() => controller.verify());

  it('adds a Bearer header when a token exists', () => {
    auth.getToken.and.returnValue('abc');
    http.get('/api/v1/admin/users').subscribe();
    const req = controller.expectOne('/api/v1/admin/users');
    expect(req.request.headers.get('Authorization')).toBe('Bearer abc');
    req.flush({});
  });

  it('sends no Authorization header without a token', () => {
    auth.getToken.and.returnValue(null);
    http.get('/api/v1/admin/users').subscribe();
    const req = controller.expectOne('/api/v1/admin/users');
    expect(req.request.headers.has('Authorization')).toBeFalse();
    req.flush({});
  });

  it('logs out on a local 401 and re-throws', () => {
    auth.getToken.and.returnValue('expired');
    let status = 0;
    http.get('/api/v1/admin/users').subscribe({ error: e => (status = e.status) });
    controller.expectOne('/api/v1/admin/users').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).toHaveBeenCalledTimes(1);
    expect(status).toBe(401);
  });

  it('does not log out on 403', () => {
    auth.getToken.and.returnValue('t');
    http.get('/api/v1/admin/users').subscribe({ error: () => undefined });
    controller.expectOne('/api/v1/admin/users').flush({}, { status: 403, statusText: 'Forbidden' });
    expect(auth.logout).not.toHaveBeenCalled();
  });

  it('does not log out on 500', () => {
    auth.getToken.and.returnValue('t');
    http.get('/api/v1/admin/users').subscribe({ error: () => undefined });
    controller.expectOne('/api/v1/admin/users').flush({}, { status: 500, statusText: 'Error' });
    expect(auth.logout).not.toHaveBeenCalled();
  });

  it('does not log out on a 401 from a peer deployment', () => {
    auth.getToken.and.returnValue('t');
    http.get('https://peer.example/api/v1/x', { context: new HttpContext().set(PEER_REQUEST, true) })
      .subscribe({ error: () => undefined });
    controller.expectOne('https://peer.example/api/v1/x').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).not.toHaveBeenCalled();
  });
});
