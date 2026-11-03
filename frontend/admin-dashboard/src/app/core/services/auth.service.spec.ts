import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { Router } from '@angular/router';
import { AuthService, AuthUser } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let router: Router;
  let httpMock: HttpTestingController;

  const b64url = (o: object) => btoa(JSON.stringify(o)).replace(/=+$/, '').replace(/\+/g, '-').replace(/\//g, '_');
  /** Unsigned stand-in for an auth-service access token; only the payload is read client-side. */
  const fakeJwt = (claims: object) => `${b64url({ alg: 'HS256', typ: 'JWT' })}.${b64url(claims)}.sig`;
  const adminToken = fakeJwt({ sub: 'u-1', roles: ['ADMIN', 'USER'], type: 'access' });

  const respond = (accessToken: string) =>
    httpMock.expectOne('/api/v1/auth/login').flush({
      accessToken,
      refreshToken: 'r',
      tokenType: 'Bearer',
      expiresIn: 3600,
      user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter', avatarUrl: null },
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
    localStorage.clear();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should not be authenticated initially', () => {
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
  });

  it('should log in an ADMIN account through the gateway', fakeAsync(() => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => { loggedInUser = user; });
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'admin@otterworks.io', password: 'admin123' });
    req.flush({
      accessToken: adminToken,
      user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter' },
    });
    tick();
    expect(loggedInUser!.token).toBe(adminToken);
    expect(loggedInUser!.id).toBe('u-1');
    expect(loggedInUser!.role).toBe('admin');
    expect(service.isAuthenticated).toBeTrue();
    expect(service.getToken()).toBe(adminToken);
    expect(localStorage.getItem('ow_admin_user')).toBeTruthy();
  }));

  it('should accept a super_admin role claim', fakeAsync(() => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => { loggedInUser = user; });
    respond(fakeJwt({ sub: 'u-1', role: 'super_admin' }));
    tick();
    expect(loggedInUser!.role).toBe('super_admin');
  }));

  it('should reject an account without the ADMIN role and store nothing', fakeAsync(() => {
    let error: Error | undefined;
    service.login('user@otterworks.io', 'pw').subscribe({ error: (e: Error) => { error = e; } });
    respond(fakeJwt({ sub: 'u-2', roles: ['USER'], type: 'access' }));
    tick();
    expect(error!.message).toBe('This account does not have admin access');
    expect(service.isAuthenticated).toBeFalse();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
  }));

  it('should not fall back to an offline token when the gateway is unreachable', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe({ error: (e: Error) => { error = e; } });
    httpMock.expectOne('/api/v1/auth/login').error(new ProgressEvent('error'));
    tick(900);
    expect(error!.message).toBe('Login failed. Please try again.');
    expect(service.getToken()).toBeNull();
  }));

  it('should report wrong credentials on 401', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', 'nope').subscribe({ error: (e: Error) => { error = e; } });
    httpMock.expectOne('/api/v1/auth/login').flush({ error: 'bad' }, { status: 401, statusText: 'Unauthorized' });
    tick();
    expect(error!.message).toBe('Invalid email or password');
    expect(service.getToken()).toBeNull();
  }));

  it('should clear auth state on logout', fakeAsync(() => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    respond(adminToken);
    tick();
    spyOn(router, 'navigate');
    service.logout();
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  }));

  it('should emit user on currentUser$ observable', fakeAsync(() => {
    const emitted: (AuthUser | null)[] = [];
    service.currentUser$.subscribe(user => emitted.push(user));
    service.login('admin@otterworks.io', 'admin123').subscribe();
    respond(adminToken);
    tick();
    expect(emitted.length).toBeGreaterThanOrEqual(2);
    expect(emitted[emitted.length - 1]).toBeTruthy();
  }));

  it('should reject login with empty password without calling the gateway', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', '').subscribe({
      error: (e: Error) => { error = e; },
    });
    httpMock.expectNone('/api/v1/auth/login');
    tick();
    expect(error!.message).toBe('Invalid credentials');
  }));
});
