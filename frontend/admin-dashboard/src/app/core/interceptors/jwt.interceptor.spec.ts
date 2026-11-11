import { TestBed } from '@angular/core/testing';
import { HTTP_INTERCEPTORS, HttpClient, HttpContext } from '@angular/common/http';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { JwtInterceptor } from './jwt.interceptor';
import { AuthService } from '../services/auth.service';
import { PEER_REQUEST } from '../services/migration-api.service';
import { MatSnackBar } from '@angular/material/snack-bar';

describe('JwtInterceptor', () => {
  let http: HttpClient;
  let ctrl: HttpTestingController;
  let auth: jasmine.SpyObj<AuthService>;
  let snackBar: jasmine.SpyObj<MatSnackBar>;

  beforeEach(() => {
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['getToken', 'logout']);
    auth.getToken.and.returnValue('tok');
    snackBar = jasmine.createSpyObj<MatSnackBar>('MatSnackBar', ['open']);
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [
        { provide: AuthService, useValue: auth },
        { provide: MatSnackBar, useValue: snackBar },
        { provide: HTTP_INTERCEPTORS, useClass: JwtInterceptor, multi: true },
      ],
    });
    http = TestBed.inject(HttpClient);
    ctrl = TestBed.inject(HttpTestingController);
  });

  afterEach(() => ctrl.verify());

  it('notifies on a local admin 403, preserves the error and keeps the session', () => {
    const onError = jasmine.createSpy('onError');
    http.get('/api/v1/admin/users').subscribe({ error: onError });
    ctrl.expectOne('/api/v1/admin/users').flush({}, { status: 403, statusText: 'Forbidden' });
    expect(snackBar.open).toHaveBeenCalledWith(
      'Access denied: your role does not permit this action', 'Dismiss', { duration: 5000 },
    );
    expect(onError).toHaveBeenCalledWith(jasmine.objectContaining({ status: 403 }));
    expect(auth.logout).not.toHaveBeenCalled();
  });

  it('does not notify for a peer admin 403', () => {
    http.get('/api/v1/admin/users', {
      context: new HttpContext().set(PEER_REQUEST, true),
    }).subscribe({ error: () => undefined });
    ctrl.expectOne('/api/v1/admin/users').flush({}, { status: 403, statusText: 'Forbidden' });
    expect(snackBar.open).not.toHaveBeenCalled();
    expect(auth.logout).not.toHaveBeenCalled();
  });

  it('does not report other API errors as role denials', () => {
    http.get('/api/v1/admin/users').subscribe({ error: () => undefined });
    ctrl.expectOne('/api/v1/admin/users').flush({}, { status: 500, statusText: 'Server error' });
    expect(snackBar.open).not.toHaveBeenCalled();
  });

  it('logs out on a 401 from the local API', () => {
    http.get('/api/v1/reports/reconciliation/latest').subscribe({ error: () => undefined });
    const req = ctrl.expectOne('/api/v1/reports/reconciliation/latest');
    expect(req.request.headers.get('Authorization')).toBe('Bearer tok');
    req.flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).toHaveBeenCalled();
  });

  it('keeps the session when the peer deployment returns 401', () => {
    http.get('https://peer.example/api/v1/reports/archive/documents/D1', {
      context: new HttpContext().set(PEER_REQUEST, true),
    }).subscribe({ error: () => undefined });
    ctrl.expectOne('https://peer.example/api/v1/reports/archive/documents/D1')
      .flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.logout).not.toHaveBeenCalled();
  });
});
