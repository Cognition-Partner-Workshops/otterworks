import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule } from '@angular/common/http/testing';
import { ActivatedRouteSnapshot, Router, RouterStateSnapshot, UrlTree, provideRouter } from '@angular/router';
import { AuthService } from '../services/auth.service';
import { authGuard } from './auth.guard';

describe('authGuard', () => {
  const route = {} as ActivatedRouteSnapshot;
  const state = { url: '/claims' } as RouterStateSnapshot;
  let auth: AuthService;

  beforeEach(() => {
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule], providers: [provideRouter([])] });
    auth = TestBed.inject(AuthService);
  });

  it('redirects to sign-in with a return URL when signed out', () => {
    spyOnProperty(auth, 'isSignedIn').and.returnValue(false);
    const result = TestBed.runInInjectionContext(() => authGuard(route, state)) as UrlTree;
    expect(TestBed.inject(Router).serializeUrl(result)).toBe('/sign-in?returnUrl=%2Fclaims');
  });

  it('allows navigation when signed in', () => {
    spyOnProperty(auth, 'isSignedIn').and.returnValue(true);
    expect(TestBed.runInInjectionContext(() => authGuard(route, state))).toBeTrue();
  });
});
