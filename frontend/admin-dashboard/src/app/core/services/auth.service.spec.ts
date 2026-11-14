import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { Router } from '@angular/router';
import { AuthService, AuthUser } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let router: Router;
  let httpMock: HttpTestingController;

  const gatewayResponse = {
    accessToken: 'server.issued.jwt',
    refreshToken: 'r',
    tokenType: 'Bearer',
    expiresIn: 3600,
    user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter', avatarUrl: null },
  };

  /** Completes the gateway login request with a server-issued token. */
  const gatewayAccepts = () => httpMock.expectOne('/api/v1/auth/login').flush(gatewayResponse);

  const expectUnauthenticated = () => {
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
    expect(localStorage.getItem('ow_admin_user')).toBeNull();
  };

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

  it('should login successfully with valid credentials', fakeAsync(() => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => {
      loggedInUser = user;
    });
    gatewayAccepts();
    tick();
    expect(loggedInUser).toBeTruthy();
    expect(loggedInUser!.email).toBe('admin@otterworks.io');
    expect(loggedInUser!.role).toBe('admin');
    expect(service.isAuthenticated).toBeTrue();
    expect(service.currentUser).toBeTruthy();
  }));

  it('should use the gateway token when /api/v1/auth/login succeeds', fakeAsync(() => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => { loggedInUser = user; });
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'admin@otterworks.io', password: 'admin123' });
    req.flush(gatewayResponse);
    tick();
    expect(loggedInUser!.token).toBe('server.issued.jwt');
    expect(loggedInUser!.id).toBe('u-1');
    expect(service.getToken()).toBe('server.issued.jwt');
  }));

  it('should store token in localStorage after login', fakeAsync(() => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    gatewayAccepts();
    tick();
    expect(localStorage.getItem('ow_admin_token')).toBe('server.issued.jwt');
    expect(localStorage.getItem('ow_admin_user')).toBeTruthy();
  }));

  it('should clear auth state on logout', fakeAsync(() => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    gatewayAccepts();
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
    gatewayAccepts();
    tick();
    expect(emitted.length).toBeGreaterThanOrEqual(2);
    expect(emitted[emitted.length - 1]).toBeTruthy();
  }));

  it('should reject invalid credentials without creating a session', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', 'wrong').subscribe({
      error: (e: Error) => { error = e; },
    });
    httpMock.expectOne('/api/v1/auth/login').flush(
      { error: 'Invalid credentials' }, { status: 401, statusText: 'Unauthorized' });
    tick(1000);
    expect(error!.message).toBe('Invalid email or password.');
    expectUnauthenticated();
  }));

  it('should not fall back to a local admin token when the gateway is unreachable', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe({
      error: (e: Error) => { error = e; },
    });
    httpMock.expectOne('/api/v1/auth/login').error(new ProgressEvent('error'));
    tick(1000);
    expect(error!.message).toBe('Unable to reach the authentication service.');
    expectUnauthenticated();
  }));

  it('should not create a session when the gateway returns a server error', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe({
      error: (e: Error) => { error = e; },
    });
    httpMock.expectOne('/api/v1/auth/login').flush(
      null, { status: 503, statusText: 'Service Unavailable' });
    tick(1000);
    expect(error!.message).toBe('Login failed. Please try again.');
    expectUnauthenticated();
  }));

  afterEach(() => {
    httpMock.verify();
  });
});
