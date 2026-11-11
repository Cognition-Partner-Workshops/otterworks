import { Injectable } from '@angular/core';
import { HttpClient, HttpErrorResponse } from '@angular/common/http';
import { BehaviorSubject, Observable, throwError } from 'rxjs';
import { tap, map, catchError } from 'rxjs/operators';
import { Router } from '@angular/router';

export interface AuthUser {
  id: string;
  email: string;
  displayName: string;
  role: string;
  token: string;
}

interface LoginResponse {
  user: AuthUser;
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

  /** Signs in against the tenant gateway so the stored bearer token is one the backends accept. */
  login(email: string, password: string): Observable<AuthUser> {
    return this.gatewayLogin(email, password).pipe(
      catchError((err: HttpErrorResponse) => throwError(() => new Error(this.loginErrorMessage(err)))),
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

  /** auth-service answers 400 for both wrong credentials and request validation, with the reason in `message`. */
  private loginErrorMessage(err: HttpErrorResponse): string {
    if (err.status === 401) {
      return 'Invalid credentials';
    }
    if (err.status === 400) {
      const message = err.error?.message;
      return typeof message === 'string' && message ? message : 'Login request was rejected.';
    }
    return 'Login service unavailable. Please try again.';
  }

  private gatewayLogin(email: string, password: string): Observable<AuthUser> {
    return this.http.post<GatewayLoginResponse>('/api/v1/auth/login', { email, password }).pipe(
      map(res => ({
        id: res.user.id,
        email: res.user.email,
        displayName: res.user.displayName || 'Admin User',
        role: 'admin',
        token: res.accessToken,
      })),
    );
  }
}
