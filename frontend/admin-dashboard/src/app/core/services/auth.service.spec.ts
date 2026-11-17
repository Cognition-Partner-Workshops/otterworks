import { TestBed } from '@angular/core/testing';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { Router } from '@angular/router';
import { AuthService, AuthUser } from './auth.service';
import { provideHttpClient, withInterceptorsFromDi, withXhr } from '@angular/common/http';

describe('AuthService', () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  let service: AuthService;
  let router: Router;

  beforeEach(() => {
    localStorage.clear();
    TestBed.configureTestingModule({
      imports: [RouterTestingModule],
      providers: [provideHttpClient(withXhr(), withInterceptorsFromDi()), provideHttpClientTesting()]
    });
    service = TestBed.inject(AuthService);
    router = TestBed.inject(Router);
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('should be created', () => {
    expect(service).toBeTruthy();
  });

  it('should not be authenticated initially', () => {
    expect(service.isAuthenticated).toBe(false);
    expect(service.currentUser).toBeNull();
  });

  it('should login successfully with valid credentials', () => {
    let loggedInUser: AuthUser | undefined;
    service.login('admin@otterworks.io', 'admin123').subscribe(user => {
      loggedInUser = user;
    });
    vi.advanceTimersByTime(900);
    expect(loggedInUser).toBeTruthy();
    expect(loggedInUser!.email).toBe('admin@otterworks.io');
    expect(loggedInUser!.role).toBe('admin');
    expect(service.isAuthenticated).toBe(true);
    expect(service.currentUser).toBeTruthy();
  });

  it('should store token in localStorage after login', () => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    vi.advanceTimersByTime(900);
    expect(localStorage.getItem('ow_admin_token')).toBeTruthy();
    expect(localStorage.getItem('ow_admin_user')).toBeTruthy();
  });

  it('should clear auth state on logout', () => {
    service.login('admin@otterworks.io', 'admin123').subscribe();
    vi.advanceTimersByTime(900);
    vi.spyOn(router, 'navigate').mockResolvedValue(true);
    service.logout();
    expect(service.isAuthenticated).toBe(false);
    expect(service.currentUser).toBeNull();
    expect(localStorage.getItem('ow_admin_token')).toBeNull();
    expect(router.navigate).toHaveBeenCalledWith(['/login']);
  });

  it('should emit user on currentUser$ observable', () => {
    const emitted: (AuthUser | null)[] = [];
    service.currentUser$.subscribe(user => emitted.push(user));
    service.login('admin@otterworks.io', 'admin123').subscribe();
    vi.advanceTimersByTime(900);
    expect(emitted.length).toBeGreaterThanOrEqual(2);
    expect(emitted[emitted.length - 1]).toBeTruthy();
  });

  it('should return token from getToken()', () => {
    expect(service.getToken()).toBeNull();
    service.login('admin@otterworks.io', 'admin123').subscribe();
    vi.advanceTimersByTime(900);
    expect(service.getToken()).toBeTruthy();
    expect(service.getToken()!.startsWith('mock-jwt-token-')).toBe(true);
  });

  it('should reject login with empty password', () => {
    let error: Error | undefined;
    service.login('admin@otterworks.io', '').subscribe({
      error: (e: Error) => { error = e; },
    });
    vi.advanceTimersByTime(900);
    expect(error).toBeTruthy();
    expect(error!.message).toBe('Invalid credentials');
  });
});
