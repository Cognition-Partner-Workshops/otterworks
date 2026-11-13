import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { PortalApiService } from '../../core/services/portal-api.service';
import { ClaimSubmitComponent } from './claim-submit.component';

describe('ClaimSubmitComponent', () => {
  let fixture: ComponentFixture<ClaimSubmitComponent>;
  let component: ClaimSubmitComponent;
  let api: jasmine.SpyObj<PortalApiService>;
  let router: Router;

  beforeEach(async () => {
    api = jasmine.createSpyObj<PortalApiService>('PortalApiService', ['submitClaim']);
    await TestBed.configureTestingModule({
      imports: [ClaimSubmitComponent],
      providers: [
        provideRouter([]),
        { provide: PortalApiService, useValue: api },
        { provide: ActivatedRoute, useValue: { snapshot: { queryParamMap: convertToParamMap({ vin: '1VSLA0000AA000001' }) } } },
      ],
    }).compileComponents();
    router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);
    fixture = TestBed.createComponent(ClaimSubmitComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('prefills the VIN from the query string', () => {
    expect(component.vin).toBe('1VSLA0000AA000001');
  });

  it('submits the claim and returns to the list', () => {
    api.submitClaim.and.returnValue(
      of({ id: 'WC-3', vin: '1VSLA0000AA000001', status: 'SUBMITTED', description: 'Door seal leaks', submittedAt: '' }),
    );
    component.vin = '1vsla0000aa000001 ';
    component.description = '  Door seal leaks ';
    component.onSubmit();
    expect(api.submitClaim).toHaveBeenCalledWith({ vin: '1VSLA0000AA000001', description: 'Door seal leaks' });
    expect(router.navigate).toHaveBeenCalledWith(['/claims']);
  });

  it('rejects a malformed VIN without calling the BFF', () => {
    component.vin = 'SHORT';
    component.description = 'Noise';
    component.onSubmit();
    expect(api.submitClaim).not.toHaveBeenCalled();
    expect(component.errorMessage).toContain('17-character VIN');
  });

  it('reports a failed submission', () => {
    api.submitClaim.and.returnValue(throwError(() => new Error('500')));
    component.description = 'Noise';
    component.onSubmit();
    expect(component.submitting).toBeFalse();
    expect(component.errorMessage).toContain('could not be submitted');
    expect(router.navigate).not.toHaveBeenCalled();
  });
});
