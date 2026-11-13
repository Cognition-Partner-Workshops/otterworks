import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { WarrantyClaim } from '../../core/models/portal.models';
import { PortalApiService } from '../../core/services/portal-api.service';
import { ClaimsListComponent } from './claims-list.component';

const CLAIMS: WarrantyClaim[] = [
  { id: 'WC-1', vin: '1VSLA0000AA000001', status: 'APPROVED', description: 'Wiper motor replaced', submittedAt: '2026-01-04T09:00:00Z' },
  { id: 'WC-2', vin: '1VSLA0000AA000002', status: 'SUBMITTED', description: 'Rattle at idle\nWorse when cold', submittedAt: '2026-02-11T15:30:00Z' },
];

describe('ClaimsListComponent', () => {
  let fixture: ComponentFixture<ClaimsListComponent>;
  let api: jasmine.SpyObj<PortalApiService>;

  async function render(): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [ClaimsListComponent],
      providers: [provideRouter([]), { provide: PortalApiService, useValue: api }],
    }).compileComponents();
    fixture = TestBed.createComponent(ClaimsListComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(() => {
    api = jasmine.createSpyObj<PortalApiService>('PortalApiService', ['claims']);
  });

  it('lists the newest claims first', async () => {
    api.claims.and.returnValue(of(CLAIMS));
    const el = await render();
    const rows = el.querySelectorAll('[data-testid="claim-row"]');
    expect(rows.length).toBe(2);
    expect(rows[0].textContent).toContain('WC-2');
    expect(rows[1].textContent).toContain('WC-1');
  });

  it('keeps line breaks in claim descriptions', async () => {
    api.claims.and.returnValue(of(CLAIMS));
    const el = await render();
    const description = el.querySelector('[data-testid="claim-row"] .description') as HTMLElement;
    expect(description.innerHTML).toBe('Rattle at idle<br>Worse when cold');
  });

  it('shows an empty state', async () => {
    api.claims.and.returnValue(of([]));
    const el = await render();
    expect(el.textContent).toContain('No warranty claims yet.');
  });

  it('shows an error when claims cannot be loaded', async () => {
    api.claims.and.returnValue(throwError(() => new Error('502')));
    const el = await render();
    expect(el.textContent).toContain('Warranty claims are unavailable right now.');
  });
});
