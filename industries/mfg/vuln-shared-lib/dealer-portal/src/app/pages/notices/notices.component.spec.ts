import { ComponentFixture, TestBed } from '@angular/core/testing';
import { of, throwError } from 'rxjs';
import { DealerNotice } from '../../core/models/portal.models';
import { PortalApiService } from '../../core/services/portal-api.service';
import { NoticesComponent } from './notices.component';

const NOTICES: DealerNotice[] = [
  { id: 'N-1', title: 'Holiday parts cut-off', severity: 'info', publishedAt: '2026-01-10T12:00:00Z', body: 'Order by Friday.' },
  { id: 'N-2', title: 'Brake hose inspection', severity: 'critical', publishedAt: '2026-02-01T12:00:00Z', body: 'Inspect <b>before</b> delivery.' },
];

describe('NoticesComponent', () => {
  let fixture: ComponentFixture<NoticesComponent>;
  let api: jasmine.SpyObj<PortalApiService>;

  async function render(): Promise<HTMLElement> {
    await TestBed.configureTestingModule({
      imports: [NoticesComponent],
      providers: [{ provide: PortalApiService, useValue: api }],
    }).compileComponents();
    fixture = TestBed.createComponent(NoticesComponent);
    fixture.detectChanges();
    return fixture.nativeElement as HTMLElement;
  }

  beforeEach(() => {
    api = jasmine.createSpyObj<PortalApiService>('PortalApiService', ['notices']);
  });

  it('shows the latest notice first with its publish date', async () => {
    api.notices.and.returnValue(of(NOTICES));
    const el = await render();
    const notices = el.querySelectorAll('[data-testid="notice"]');
    expect(notices.length).toBe(2);
    expect(notices[0].querySelector('h2')?.textContent).toBe('Brake hose inspection');
    expect(notices[0].querySelector('time')?.textContent).toBe('1 Feb 2026');
  });

  it('renders notice bodies as text', async () => {
    api.notices.and.returnValue(of(NOTICES));
    const el = await render();
    const body = el.querySelector('[data-testid="notice"] .body') as HTMLElement;
    expect(body.textContent).toBe('Inspect <b>before</b> delivery.');
    expect(body.querySelector('b')).toBeNull();
  });

  it('shows an error when the feed is unavailable', async () => {
    api.notices.and.returnValue(throwError(() => new Error('502')));
    const el = await render();
    expect(el.textContent).toContain('Dealer notices are unavailable right now.');
  });
});
