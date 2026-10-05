import { ComponentFixture, TestBed } from '@angular/core/testing';
import { RouterTestingModule } from '@angular/router/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of, throwError } from 'rxjs';
import { AdminApiService } from '../../core/services/admin-api.service';
import { User } from '../../core/models/user.model';
import { UsersComponent } from './users.component';

describe('UsersComponent', () => {
  let component: UsersComponent;
  let fixture: ComponentFixture<UsersComponent>;
  let api: jasmine.SpyObj<AdminApiService>;

  const user: User = {
    id: 'user-1',
    email: 'user@example.com',
    displayName: 'Test User',
    role: 'admin',
    status: 'active',
    storageUsed: 0,
    storageQuota: 1024,
    lastLogin: '2026-01-01T00:00:00Z',
    createdAt: '2026-01-01T00:00:00Z',
    documentsCount: 0,
  };

  beforeEach(async () => {
    api = jasmine.createSpyObj<AdminApiService>('AdminApiService', ['getUsers', 'getStorageUsage']);
    api.getUsers.and.returnValue(of([user]));
    api.getStorageUsage.and.returnValue(of({
      totalBytes: 2048,
      fileCount: 3,
      storageUsed: '2 KB',
      byUser: { 'user-1': { fileCount: 3, totalBytes: 2048 } },
    }));

    await TestBed.configureTestingModule({
      imports: [
        UsersComponent,
        RouterTestingModule,
        NoopAnimationsModule,
      ],
      providers: [{ provide: AdminApiService, useValue: api }],
    }).compileComponents();

    fixture = TestBed.createComponent(UsersComponent);
    component = fixture.componentInstance;
  });

  it('creates and loads users', () => {
    expect(component).toBeTruthy();
    expect(component.loading).toBeTrue();
    fixture.detectChanges();
    expect(component.loading).toBeFalse();
    expect(component.dataSource.data.length).toBe(1);
    expect(component.dataSource.data[0].fileCount).toBe(3);
  });

  it('adds a sortable Files column after the existing columns', () => {
    expect(component.displayedColumns).toEqual([
      'displayName', 'role', 'status', 'department', 'lastLogin', 'fileCount', 'actions',
    ]);
    fixture.detectChanges();

    const headers = Array.from(fixture.nativeElement.querySelectorAll('th[mat-sort-header]')) as HTMLElement[];
    const header = headers.find(element => element.textContent?.trim() === 'Files');
    expect(header).toBeTruthy();
    const fileCell = fixture.nativeElement.querySelector('td.mat-column-fileCount') as HTMLElement;
    expect(fileCell.textContent?.trim()).toBe('3');
  });

  it('shows an em dash when the usage request fails', () => {
    api.getStorageUsage.and.returnValue(throwError(() => new Error('file service unavailable')));
    fixture.detectChanges();

    const fileCell = fixture.nativeElement.querySelector('td.mat-column-fileCount') as HTMLElement;
    expect(fileCell.textContent?.trim()).toBe('—');
  });

  it('applies a text filter and displays the page title', () => {
    fixture.detectChanges();

    const event = { target: { value: 'test user' } } as unknown as Event;
    component.applyFilter(event);
    expect(component.dataSource.filter).toBe('test user');
    expect(fixture.nativeElement.textContent).toContain('User Management');
  });
});
