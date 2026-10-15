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

  /**
   * Signs in against auth-service through the gateway. Only a server-issued token is ever stored;
   * any failure leaves the session unauthenticated.
   */
  login(email: string, password: string): Observable<AuthUser> {
    return this.gatewayLogin(email, password).pipe(
      catchError((err: unknown) => throwError(() => new Error(this.loginErrorMessage(err)))),
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
      map(res => ({
        id: res.user.id,
        email: res.user.email,
        displayName: res.user.displayName || 'Admin User',
        role: 'admin',
        token: res.accessToken,
      })),
    );
  }

  private loginErrorMessage(err: unknown): string {
    if (err instanceof HttpErrorResponse) {
      if (err.status === 400 || err.status === 401 || err.status === 403) {
        return 'Invalid email or password.';
      }
      if (err.status === 0) {
        return 'Unable to reach the authentication service.';
      }
    }
    return 'Login failed. Please try again.';
  }
}
