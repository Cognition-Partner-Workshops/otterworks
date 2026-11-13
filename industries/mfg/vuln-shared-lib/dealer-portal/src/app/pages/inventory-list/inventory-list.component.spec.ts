import { ComponentFixture, TestBed } from '@angular/core/testing';
import { ActivatedRoute, Router, convertToParamMap, provideRouter } from '@angular/router';
import { BehaviorSubject, of } from 'rxjs';
import { Vehicle } from '../../core/models/portal.models';
import { PortalApiService } from '../../core/services/portal-api.service';
import { InventoryListComponent } from './inventory-list.component';

const INVENTORY: Vehicle[] = [
  { vin: '1VSLA0000AA000001', model: 'Ranger LT', year: 2026, status: 'AVAILABLE', priceCents: 3899000, imageUrl: '' },
  { vin: '1VSLA0000AA000002', model: 'Harbor XL', year: 2025, status: 'SOLD', priceCents: 4525000, imageUrl: '' },
  { vin: '1VSLA0000AA000003', model: 'Ranger Sport', year: 2026, status: 'IN_TRANSIT', priceCents: 4100000, imageUrl: '' },
];

describe('InventoryListComponent', () => {
  let fixture: ComponentFixture<InventoryListComponent>;
  let params: BehaviorSubject<ReturnType<typeof convertToParamMap>>;

  beforeEach(async () => {
    params = new BehaviorSubject(convertToParamMap({}));
    await TestBed.configureTestingModule({
      imports: [InventoryListComponent],
      providers: [
        provideRouter([]),
        { provide: PortalApiService, useValue: { inventory: () => of(INVENTORY) } },
        { provide: ActivatedRoute, useValue: { queryParamMap: params } },
      ],
    }).compileComponents();
    fixture = TestBed.createComponent(InventoryListComponent);
    fixture.detectChanges();
  });

  const rows = () => (fixture.nativeElement as HTMLElement).querySelectorAll('[data-testid="vehicle-row"]');
  const summary = () => (fixture.nativeElement as HTMLElement).querySelector('[data-testid="search-summary"]') as HTMLElement;

  it('lists every vehicle without a search term', () => {
    expect(rows().length).toBe(3);
    expect(summary().hidden).toBeTrue();
  });

  it('filters by model from the q query parameter', () => {
    params.next(convertToParamMap({ q: 'ranger' }));
    fixture.detectChanges();
    expect(rows().length).toBe(2);
    expect(summary().textContent).toBe('2 vehicles match ranger');
    expect(summary().querySelector('strong')?.textContent).toBe('ranger');
  });

  it('filters by VIN', () => {
    params.next(convertToParamMap({ q: '000002' }));
    fixture.detectChanges();
    expect(rows().length).toBe(1);
    expect(summary().textContent).toBe('1 vehicle matches 000002');
  });

  it('formats prices in dollars', () => {
    expect(rows()[0].textContent).toContain('$38,990.00');
  });

  it('puts the search term in the URL', () => {
    const router = TestBed.inject(Router);
    spyOn(router, 'navigate').and.resolveTo(true);
    fixture.componentInstance.searchText = ' harbor ';
    fixture.componentInstance.search();
    expect(router.navigate).toHaveBeenCalledWith([], jasmine.objectContaining({ queryParams: { q: 'harbor' } }));
  });
});
