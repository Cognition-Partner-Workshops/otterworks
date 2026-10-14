import { TestBed, fakeAsync, tick } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { Router } from '@angular/router';
import { AuthService, AuthUser } from './auth.service';

describe('QA AuthService (gateway login + mock fallback)', () => {
  let service: AuthService;
  let http: HttpTestingController;
  let router: jasmine.SpyObj<Router>;

  beforeEach(() => {
    localStorage.clear();
    router = jasmine.createSpyObj('Router', ['navigate']);
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
      providers: [{ provide: Router, useValue: router }],
    });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    localStorage.clear();
  });

  it('starts unauthenticated with an empty store', () => {
    expect(service.isAuthenticated).toBeFalse();
    expect(service.currentUser).toBeNull();
    expect(service.getToken()).toBeNull();
  });

  it('POSTs credentials to the gateway and stores the returned access token', () => {
    let user: AuthUser | undefined;
    service.login('qa@otterworks.io', 'pw').subscribe(u => (user = u));
    const req = http.expectOne('/api/v1/auth/login');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'qa@otterworks.io', password: 'pw' });
    req.flush({ accessToken: 'gateway-token', user: { id: 'g-1', email: 'qa@otterworks.io', displayName: 'QA' } });
    expect(user!.token).toBe('gateway-token');
    expect(user!.id).toBe('g-1');
    expect(localStorage.getItem('ow_admin_token')).toBe('gateway-token');
    expect(JSON.parse(localStorage.getItem('ow_admin_user')!).email).toBe('qa@otterworks.io');
    expect(service.isAuthenticated).toBeTrue();
  });

  it('defaults displayName to "Admin User" when the gateway omits it', () => {
    let user: AuthUser | undefined;
    service.login('qa@otterworks.io', 'pw').subscribe(u => (user = u));
    http.expectOne('/api/v1/auth/login').flush({ accessToken: 't', user: { id: 'g', email: 'qa@otterworks.io', displayName: '' } });
    expect(user!.displayName).toBe('Admin User');
  });

  it('falls back to the offline mock user after ~800ms when the gateway rejects', fakeAsync(() => {
    let user: AuthUser | undefined;
    service.login('someone@otterworks.io', 'wrong').subscribe(u => (user = u));
    http.expectOne('/api/v1/auth/login').flush({}, { status: 401, statusText: 'Unauthorized' });
    tick(799);
    expect(user).toBeUndefined();
    tick(1);
    expect(user!.id).toBe('a0000000-0000-0000-0000-000000000001');
    expect(user!.email).toBe('someone@otterworks.io');
    expect(service.isAuthenticated).toBeTrue();
  }));

  it('rejects an empty password when the gateway is unavailable', fakeAsync(() => {
    let error: Error | undefined;
    service.login('qa@otterworks.io', '').subscribe({ error: e => (error = e) });
    http.expectOne('/api/v1/auth/login').error(new ProgressEvent('network'));
    tick(1000);
    expect(error?.message).toBe('Invalid credentials');
    expect(service.isAuthenticated).toBeFalse();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
  }));

  it('emits the logged-in user on currentUser$', () => {
    const seen: (AuthUser | null)[] = [];
    service.currentUser$.subscribe(u => seen.push(u));
    service.login('qa@otterworks.io', 'pw').subscribe();
    http.expectOne('/api/v1/auth/login').flush({ accessToken: 't', user: { id: 'g', email: 'qa@otterworks.io', displayName: 'QA' } });
    expect(seen[0]).toBeNull();
    expect(seen[seen.length - 1]?.email).toBe('qa@otterworks.io');
  });

  it('logout clears storage, emits null and navigates to /login', () => {
    localStorage.setItem('ow_admin_token', 't');
    localStorage.setItem('ow_admin_user', JSON.stringify({ id: '1' }));
    service.logout();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
    expect(localStorage.getItem('ow_admin_user')).toBeNull();
    expect(service.currentUser).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('restores a stored user on construction and tolerates corrupt JSON', () => {
    localStorage.setItem('ow_admin_user', JSON.stringify({ id: 'stored', email: 'e' }));
    expect(new AuthService(TestBed.inject(HttpClientTestingModule as any) as any, router).currentUser?.id).toBe('stored');
    localStorage.setItem('ow_admin_user', '{not json');
    expect(new AuthService({} as any, router).currentUser).toBeNull();
  });
});
