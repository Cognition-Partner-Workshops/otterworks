import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { BehaviorSubject, Observable } from 'rxjs';
import { finalize, tap } from 'rxjs/operators';
import { environment } from '../../../environments/environment';
import { PortalSession } from '../models/portal.models';

const SESSION_KEY = 'dp_session';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly sessionSubject = new BehaviorSubject<PortalSession | null>(AuthService.readStored());
  readonly session$ = this.sessionSubject.asObservable();

  constructor(private http: HttpClient) {}

  get session(): PortalSession | null {
    const current = this.sessionSubject.value;
    if (current && Date.parse(current.expiresAt) <= Date.now()) {
      this.clear();
      return null;
    }
    return current;
  }

  get isSignedIn(): boolean {
    return this.session !== null;
  }

  signIn(email: string, password: string): Observable<PortalSession> {
    return this.http
      .post<PortalSession>(`${environment.bffBaseUrl}/session`, { email, password })
      .pipe(tap(session => this.store(session)));
  }

  signOut(): Observable<void> {
    return this.http.delete<void>(`${environment.bffBaseUrl}/session`).pipe(finalize(() => this.clear()));
  }

  clear(): void {
    sessionStorage.removeItem(SESSION_KEY);
    this.sessionSubject.next(null);
  }

  private store(session: PortalSession): void {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
    this.sessionSubject.next(session);
  }

  private static readStored(): PortalSession | null {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) {
      return null;
    }
    try {
      return JSON.parse(raw) as PortalSession;
    } catch {
      sessionStorage.removeItem(SESSION_KEY);
      return null;
    }
  }
}
