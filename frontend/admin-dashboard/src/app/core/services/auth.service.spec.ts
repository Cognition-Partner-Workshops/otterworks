import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { Router } from '@angular/router';
import { AuthService, AuthUser } from './auth.service';

describe('AuthService', () => {
  let service: AuthService;
  let router: Router;
  let httpMock: HttpTestingController;

  const gatewayOk = () =>
    httpMock.expectOne('/api/v1/auth/login').flush({
      accessToken: 'gateway.jwt.token',
      refreshToken: 'r',
      tokenType: 'Bearer',
      expiresIn: 3600,
      user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter', avatarUrl: null },
    });

  const gatewayRejects = (status: number) =>
    httpMock
      .expectOne('/api/v1/auth/login')
      .flush({ error: 'Invalid credentials' }, { status, statusText: 'Rejected' });

  const expectNothingStored = () => {
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
    httpMock.verify();
    localStorage.clear();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should not be authenticated initially', () => {
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
  });

  it('should use the gateway token when /api/v1/auth/login succeeds', fakeAsync(() => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => { loggedInUser = user; });
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'admin@otterworks.io', password: 'admin123' });
    req.flush({
      accessToken: 'gateway.jwt.token',
      refreshToken: 'r',
      tokenType: 'Bearer',
      expiresIn: 3600,
      user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter', avatarUrl: null },
    });
    tick();
    expect(loggedInUser!.token).toBe('gateway.jwt.token');
    expect(loggedInUser!.id).toBe('u-1');
    expect(loggedInUser!.role).toBe('admin');
    expect(service.getToken()).toBe('gateway.jwt.token');
    expect(service.isAuthenticated).toBeTrue();
    expect(JSON.parse(localStorage.getItem('ow_admin_user')!).id).toBe('u-1');
  }));

  it('should reject a 401 from the gateway and store no token', fakeAsync(() => {
    const result = { error: undefined as Error | undefined };
    service.login('admin@otterworks.io', 'wrong-password').subscribe({
      next: () => fail('login must not succeed'),
      error: (e: Error) => { result.error = e; },
    });
    gatewayRejects(401);
    tick(1000);
    expect(result.error?.message).toBe('Invalid email or password.');
    expectNothingStored();
  }));

  it('should reject a 400 invalid-credentials response and store no token', fakeAsync(() => {
    const result = { error: undefined as Error | undefined };
    service.login('admin@otterworks.io', 'wrong-password').subscribe({
      error: (e: Error) => { result.error = e; },
    });
    gatewayRejects(400);
    tick(1000);
    expect(result.error?.message).toBe('Invalid email or password.');
    expectNothingStored();
  }));

  it('should fail, not fall back to a built-in user, when the gateway is unreachable', fakeAsync(() => {
    const result = { error: undefined as Error | undefined };
    service.login('admin@otterworks.io', 'any-password').subscribe({
      error: (e: Error) => { result.error = e; },
    });
    httpMock.expectOne('/api/v1/auth/login').error(new ProgressEvent('error'));
    tick(1000);
    expect(result.error?.message).toBe('Unable to reach the sign-in service. Please try again.');
    expectNothingStored();
  }));

  it('should fail on a gateway 5xx and store no token', fakeAsync(() => {
    const result = { error: undefined as Error | undefined };
    service.login('admin@otterworks.io', 'any-password').subscribe({
      error: (e: Error) => { result.error = e; },
    });
    gatewayRejects(502);
    tick(1000);
    expect(result.error?.message).toBe('Login failed. Please try again.');
    expectNothingStored();
  }));

  it('should clear auth state on logout', fakeAsync(() => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    gatewayOk();
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
    gatewayOk();
    tick();
    expect(emitted.length).toBeGreaterThanOrEqual(2);
    expect(emitted[emitted.length - 1]?.token).toBe('gateway.jwt.token');
  }));
});
