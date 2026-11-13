import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { SignInComponent } from './sign-in.component';

describe('SignInComponent', () => {
  let fixture: ComponentFixture<SignInComponent>;
  let component: SignInComponent;
  let auth: jasmine.SpyObj<AuthService>;
  let router: Router;
  let returnUrl: string | null;

  beforeEach(async () => {
    returnUrl = null;
    auth = jasmine.createSpyObj<AuthService>('AuthService', ['signIn']);
    await TestBed.configureTestingModule({
      imports: [SignInComponent],
      providers: [
        provideRouter([]),
        { provide: AuthService, useValue: auth },
        {
          provide: ActivatedRoute,
          useValue: { snapshot: { get queryParamMap() { return convertToParamMap(returnUrl ? { returnUrl } : {}); } } },
        },
      ],
    }).compileComponents();
    router = TestBed.inject(Router);
    spyOn(router, 'navigateByUrl').and.resolveTo(true);
    fixture = TestBed.createComponent(SignInComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('renders the sign-in form', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('input[type="email"]')).toBeTruthy();
    expect(el.querySelector('input[type="password"]')).toBeTruthy();
    expect(el.querySelector('button[type="submit"]')?.textContent).toContain('Sign in');
  });

  it('does not call the BFF with empty fields', () => {
    component.onSubmit();
    expect(auth.signIn).not.toHaveBeenCalled();
  });

  it('navigates to inventory after signing in', () => {
    auth.signIn.and.returnValue(of({ email: 'dealer-ops@dealer.example', dealerId: 'D-1001', expiresAt: '' }));
    component.email = 'dealer-ops@dealer.example';
    component.password = 'vsl-synthetic-portal-pass';
    component.onSubmit();
    expect(auth.signIn).toHaveBeenCalledWith('dealer-ops@dealer.example', 'vsl-synthetic-portal-pass');
    expect(router.navigateByUrl).toHaveBeenCalledWith('/inventory');
  });

  it('honours a local return URL', () => {
    returnUrl = '/claims';
    auth.signIn.and.returnValue(of({ email: 'a@dealer.example', dealerId: 'D-1001', expiresAt: '' }));
    component.email = 'a@dealer.example';
    component.password = 'x';
    component.onSubmit();
    expect(router.navigateByUrl).toHaveBeenCalledWith('/claims');
  });

  it('shows an error when sign-in fails', () => {
    auth.signIn.and.returnValue(throwError(() => new Error('401')));
    component.email = 'dealer-ops@dealer.example';
    component.password = 'wrong';
    component.onSubmit();
    fixture.detectChanges();
    expect(component.loading).toBeFalse();
    expect((fixture.nativeElement as HTMLElement).querySelector('[role="alert"]')?.textContent).toContain('Sign-in failed');
  });
});
