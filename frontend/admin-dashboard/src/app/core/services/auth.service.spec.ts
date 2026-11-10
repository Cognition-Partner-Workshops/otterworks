import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { HttpErrorResponse } from '@angular/common/http';
import { RouterTestingModule } from '@angular/router/testing';
import { Router } from '@angular/router';
import { AuthService, AuthUser } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let router: Router;
  let httpMock: HttpTestingController;

  const gatewaySuccess = () => httpMock.expectOne('/api/v1/auth/login').flush({
    accessToken: 'gateway.jwt.token',
    user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter' },
  });

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule, RouterTestingModule],
    });
    service = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
    localStorage.clear();
  });

  it('should be created without an authenticated user', () => {
    expect(service).toBeTruthy();
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
    expect(service.getToken()).toBeNull();
  });

  it('should use and store the gateway response on successful login', () => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'input').subscribe(user => { loggedInUser = user; });
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'admin@otterworks.io', password: 'input' });
    req.flush({
      accessToken: 'gateway.jwt.token',
      user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter' },
    });
    expect(loggedInUser!.id).toBe('u-1');
    expect(service.currentUser).toEqual(loggedInUser!);
    expect(service.isAuthenticated).toBeTrue();
    expect(service.getToken()).toBe('gateway.jwt.token');
    expect(localStorage.getItem('ow_admin_user')).toBe(JSON.stringify(loggedInUser));
  });

  it('should clear auth state on logout', () => {
    service.login('admin@otterworks.io', 'input').subscribe();
    gatewaySuccess();
    spyOn(router, 'navigate');
    service.logout();
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
    expect(localStorage.getItem('ow_admin_user')).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('should emit the gateway user', () => {
    const emitted: (AuthUser | null)[] = [];
    service.currentUser$.subscribe(user => emitted.push(user));
    service.login('admin@otterworks.io', 'input').subscribe();
    gatewaySuccess();
    expect(emitted.length).toBe(2);
    expect(emitted[0]).toBeNull();
    expect(emitted[1]!.id).toBe('u-1');
  });

  it('should surface a network error without creating an offline session', () => {
    let error: HttpErrorResponse | undefined;
    service.login('admin@otterworks.io', 'input').subscribe({ error: e => { error = e; } });
    httpMock.expectOne('/api/v1/auth/login').error(new ProgressEvent('error'));
    expect(error!.status).toBe(0);
    expect(service.currentUser).toBeNull();
    expect(service.isAuthenticated).toBeFalse();
    expect(localStorage.length).toBe(0);
  });

  it('should surface rejected credentials including an empty password', () => {
    let error: HttpErrorResponse | undefined;
    service.login('admin@otterworks.io', '').subscribe({ error: e => { error = e; } });
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.body.password).toBe('');
    req.flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(error!.status).toBe(401);
    expect(service.currentUser).toBeNull();
    expect(service.isAuthenticated).toBeFalse();
    expect(localStorage.length).toBe(0);
  });
});
