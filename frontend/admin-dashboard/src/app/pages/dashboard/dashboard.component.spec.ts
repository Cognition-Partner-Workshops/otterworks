import { ComponentFixture, TestBed } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of, Subject, throwError } from 'rxjs';
import { AdminApiService } from '../../core/services/admin-api.service';
import { DashboardComponent } from './dashboard.component';

describe('DashboardComponent', () => {
  let component: DashboardComponent;
  let fixture: ComponentFixture<DashboardComponent>;
  let api: jasmine.SpyObj<AdminApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<AdminApiService>(
      'AdminApiService',
      ['getDashboardStats', 'getStorageUsage', 'getAnalyticsReport'],
      { statsChanged$: new Subject<void>() },
    );
    api.getDashboardStats.and.returnValue(of({
      totalUsers: 1,
      activeDocuments: 0,
      storageUsed: '0 B',
      activeSessions: 1,
      usersGrowth: 0,
      documentsGrowth: 0,
      storageGrowth: 0,
      sessionsGrowth: 0,
    }));
    api.getStorageUsage.and.returnValue(of({
      totalBytes: 1536,
      fileCount: 2,
      storageUsed: '1.5 KB',
      byUser: {},
    }));
    api.getAnalyticsReport.and.returnValue(of({
      userSignups: [],
      storageUsage: [],
      documentActivity: [],
      activeUsers: [],
      topFileTypes: [],
      peakHours: [],
    }));

    await TestBed.configureTestingModule({
      imports: [
        DashboardComponent,
        NoopAnimationsModule,
      ],
      providers: [{ provide: AdminApiService, useValue: api }],
    }).compileComponents();

    fixture = TestBed.createComponent(DashboardComponent);
    component = fixture.componentInstance;
  });

  it('creates and loads dashboard stats', () => {
    expect(component).toBeTruthy();
    fixture.detectChanges();
    expect(component.loading).toBeFalse();
    expect(component.stats?.totalUsers).toBe(1);
    expect(fixture.nativeElement.textContent).toContain('Dashboard');
    expect(fixture.nativeElement.querySelectorAll('.stat-card').length).toBe(4);
  });

  it('renders the storage used label and formatted usage', () => {
    fixture.detectChanges();

    const cards = Array.from(fixture.nativeElement.querySelectorAll('.stat-card')) as HTMLElement[];
    const storageCard = cards.find(card =>
      card.querySelector('.stat-label')?.textContent?.trim() === 'Storage used',
    );

    expect(storageCard).toBeTruthy();
    expect(storageCard?.querySelector('.stat-value')?.textContent?.trim()).toBe('1.5 KB');
    expect(storageCard?.querySelector('.stat-subtitle')?.textContent?.trim()).toBe('2 files');
    expect(storageCard?.querySelector('.stat-growth')).toBeNull();
  });

  it('shows Unavailable for a failed usage request without affecting other tiles', () => {
    api.getStorageUsage.and.returnValue(throwError(() => new Error('file service unavailable')));
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Unavailable');
    expect(compiled.textContent).toContain('Total Users');
    expect(component.loading).toBeFalse();
  });
});
