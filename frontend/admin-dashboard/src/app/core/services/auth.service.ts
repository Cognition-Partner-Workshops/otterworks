import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, of, throwError } from 'rxjs';
import { tap, switchMap, catchError } from 'rxjs/operators';
import { Router } from '@angular/router';

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
  role: string;
  token: string;
}

/** auth-service AuthResponse as proxied by the gateway at /api/v1/auth/login. */
interface GatewayLoginResponse {
  accessToken: string;
  user: { id: string; email: string; displayName: string };
}

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly TOKEN_KEY = 'ow_admin_token';
  private readonly USER_KEY = 'ow_admin_user';
  private currentUserSubject = new BehaviorSubject<AuthUser | null>(this.getStoredUser());
  currentUser$ = this.currentUserSubject.asObservable();

  constructor(private http: HttpClient, private router: Router) {}

  get isAuthenticated(): boolean {
    return !!this.getToken();
  }

  get currentUser(): AuthUser | null {
    return this.currentUserSubject.value;
  }

  getToken(): string | null {
    return localStorage.getItem(this.TOKEN_KEY);
  }

  /**
   * Signs in through the gateway (auth-service). Only accounts whose access token carries the
   * ADMIN (or SUPER_ADMIN) role are let in; admin-service enforces the same rule server-side.
   */
  login(email: string, password: string): Observable<AuthUser> {
    if (!email || !password) {
      return throwError(() => new Error('Invalid credentials'));
    }
    return this.gatewayLogin(email, password).pipe(
      tap(user => {
        localStorage.setItem(this.TOKEN_KEY, user.token);
        localStorage.setItem(this.USER_KEY, JSON.stringify(user));
        this.currentUserSubject.next(user);
      })
    );
  }

  logout(): void {
    localStorage.removeItem(this.TOKEN_KEY);
    localStorage.removeItem(this.USER_KEY);
    this.currentUserSubject.next(null);
    this.router.navigate(['/login']);
  }

  private getStoredUser(): AuthUser | null {
    const stored = localStorage.getItem(this.USER_KEY);
    if (stored) {
      try {
        return JSON.parse(stored) as AuthUser;
      } catch {
        return null;
      }
    }
    return null;
  }

  private gatewayLogin(email: string, password: string): Observable<AuthUser> {
    return this.http.post<GatewayLoginResponse>('/api/v1/auth/login', { email, password }).pipe(
      catchError((err: HttpErrorResponse) =>
        throwError(() => new Error(err.status === 401 ? 'Invalid email or password' : 'Login failed. Please try again.'))
      ),
      switchMap(res => {
        const role = adminRole(res.accessToken);
        if (!role) {
          return throwError(() => new Error('This account does not have admin access'));
        }
        return of({
          id: res.user.id,
          email: res.user.email,
          displayName: res.user.displayName || 'Admin User',
          role,
          token: res.accessToken,
        });
      }),
    );
  }
}

/** Returns 'super_admin' or 'admin' when the JWT's role claims grant admin access, else null. */
function adminRole(token: string): string | null {
  let claims: { role?: unknown; roles?: unknown };
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
    claims = JSON.parse(atob(payload));
  } catch {
    return null;
  }
  const roles = [claims.role, ...(Array.isArray(claims.roles) ? claims.roles : [])]
    .filter((r): r is string => typeof r === 'string')
    .map(r => r.toLowerCase());
  if (roles.includes('super_admin')) return 'super_admin';
  return roles.includes('admin') ? 'admin' : null;
}
