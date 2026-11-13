import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AuthService } from './auth.service';
import { PortalSession } from '../models/portal.models';

describe('AuthService', () => {
  let service: AuthService;
  let http: HttpTestingController;

  const session: PortalSession = {
    email: 'dealer-ops@dealer.example',
    dealerId: 'D-1001',
    expiresAt: new Date(Date.now() + 3600_000).toISOString(),
  };

  beforeEach(() => {
    sessionStorage.clear();
    TestBed.configureTestingModule({ imports: [HttpClientTestingModule] });
    service = TestBed.inject(AuthService);
    http = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    http.verify();
    sessionStorage.clear();
  });

  it('starts signed out', () => {
    expect(service.isSignedIn).toBeFalse();
    expect(service.session).toBeNull();
  });

  it('posts credentials to the BFF and stores the session', () => {
    let result: PortalSession | undefined;
    service.signIn('dealer-ops@dealer.example', 'vsl-synthetic-portal-pass').subscribe(s => (result = s));

    const req = http.expectOne('/bff/session');
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ email: 'dealer-ops@dealer.example', password: 'vsl-synthetic-portal-pass' });
    req.flush(session);

    expect(result).toEqual(session);
    expect(service.isSignedIn).toBeTrue();
    expect(JSON.parse(sessionStorage.getItem('dp_session')!)).toEqual(session);
  });

  it('does not store anything when sign-in fails', () => {
    service.signIn('dealer-ops@dealer.example', 'wrong').subscribe({ error: () => undefined });
    http.expectOne('/bff/session').flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(service.isSignedIn).toBeFalse();
    expect(sessionStorage.getItem('dp_session')).toBeNull();
  });

  it('clears the session on sign-out even when the BFF call fails', () => {
    service.signIn('dealer-ops@dealer.example', 'vsl-synthetic-portal-pass').subscribe();
    http.expectOne('/bff/session').flush(session);

    service.signOut().subscribe({ error: () => undefined });
    const req = http.expectOne('/bff/session');
    expect(req.request.method).toBe('DELETE');
    req.flush({}, { status: 500, statusText: 'Server Error' });

    expect(service.isSignedIn).toBeFalse();
    expect(sessionStorage.getItem('dp_session')).toBeNull();
  });

  it('treats an expired stored session as signed out', () => {
    service.signIn('dealer-ops@dealer.example', 'vsl-synthetic-portal-pass').subscribe();
    http.expectOne('/bff/session').flush({ ...session, expiresAt: '2020-01-01T00:00:00Z' });
    expect(service.isSignedIn).toBeFalse();
  });
});
