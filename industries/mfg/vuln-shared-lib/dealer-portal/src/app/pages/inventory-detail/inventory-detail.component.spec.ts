import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { of, throwError } from 'rxjs';
import { PortalApiService } from '../../core/services/portal-api.service';
import { InventoryDetailComponent } from './inventory-detail.component';

describe('InventoryDetailComponent', () => {
  let fixture: ComponentFixture<InventoryDetailComponent>;
  let api: jasmine.SpyObj<PortalApiService>;

  beforeEach(async () => {
    api = jasmine.createSpyObj<PortalApiService>('PortalApiService', ['vehicle']);
    await TestBed.configureTestingModule({
      imports: [InventoryDetailComponent],
      providers: [provideRouter([]), { provide: PortalApiService, useValue: api }],
    }).compileComponents();
    fixture = TestBed.createComponent(InventoryDetailComponent);
  });

  it('loads the vehicle for the VIN in the route', () => {
    api.vehicle.and.returnValue(
      of({ vin: '1VSLA0000AA000001', model: 'Ranger LT', year: 2026, status: 'AVAILABLE', priceCents: 3899000, imageUrl: 'favicon.ico' }),
    );
    fixture.componentRef.setInput('vin', '1VSLA0000AA000001');
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(api.vehicle).toHaveBeenCalledWith('1VSLA0000AA000001');
    expect(el.querySelector('h1')?.textContent).toContain('2026 Ranger LT');
    expect(el.querySelector('[data-testid="vehicle-vin"]')?.textContent).toBe('1VSLA0000AA000001');
    expect(el.querySelector('a[href^="/claims/new"]')?.getAttribute('href')).toBe('/claims/new?vin=1VSLA0000AA000001');
  });

  it('shows a message for an unknown VIN', () => {
    api.vehicle.and.returnValue(throwError(() => new Error('404')));
    fixture.componentRef.setInput('vin', 'NOPE');
    fixture.detectChanges();
    expect((fixture.nativeElement as HTMLElement).textContent).toContain('Vehicle NOPE was not found');
  });
});
