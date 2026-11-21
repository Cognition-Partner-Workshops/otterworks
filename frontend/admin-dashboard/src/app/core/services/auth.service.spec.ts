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
    accessToken: 'gateway.jwt.token',
    refreshToken: 'r',
    tokenType: 'Bearer',
    expiresIn: 3600,
    user: { id: 'u-1', email: 'admin@otterworks.io', displayName: 'Presenter', avatarUrl: null },
  };

  /** Answers the gateway login request with an issued token. */
  const gatewayAccepts = () => httpMock.expectOne('/api/v1/auth/login').flush(gatewayResponse);

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

  it('should login with the token the gateway issues', fakeAsync(() => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => { loggedInUser = user; });
    const req = httpMock.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'admin@otterworks.io', password: 'admin123' });
    req.flush(gatewayResponse);
    tick();
    expect(loggedInUser!.token).toBe('gateway.jwt.token');
    expect(loggedInUser!.id).toBe('u-1');
    expect(loggedInUser!.email).toBe('admin@otterworks.io');
    expect(loggedInUser!.role).toBe('admin');
    expect(service.isAuthenticated).toBeTrue();
    expect(service.getToken()).toBe('gateway.jwt.token');
  }));

  it('should store token in localStorage after login', fakeAsync(() => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    gatewayAccepts();
    tick();
    expect(localStorage.getItem('ow_admin_token')).toBe('gateway.jwt.token');
    expect(localStorage.getItem('ow_admin_user')).toBeTruthy();
  }));

  it('should reject login when the gateway rejects the credentials', fakeAsync(() => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', 'wrong').subscribe({
      error: (e: Error) => { error = e; },
    });
    httpMock.expectOne('/api/v1/auth/login').flush({ message: 'Invalid credentials' }, { status: 401, statusText: 'Unauthorized' });
    tick();
    expect(error!.message).toBe('Invalid credentials');
    expect(service.isAuthenticated).toBeFalse();
    expect(service.getToken()).toBeNull();
  }));

  it('should fail closed when the gateway is unreachable instead of minting a token itself', fakeAsync(() => {
    let error: Error | undefined;
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe({
      next: user => { loggedInUser = user; },
      error: (e: Error) => { error = e; },
    });
    httpMock.expectOne('/api/v1/auth/login').error(new ProgressEvent('error'));
    tick(1000);
    expect(loggedInUser).toBeUndefined();
    expect(error).toBeTruthy();
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
    expect(localStorage.getItem('ow_admin_user')).toBeNull();
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
    expect(emitted[emitted.length - 1]!.token).toBe('gateway.jwt.token');
  }));
});
