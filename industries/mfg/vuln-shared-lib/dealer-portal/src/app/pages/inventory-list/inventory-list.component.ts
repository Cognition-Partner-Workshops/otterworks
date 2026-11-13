import { Component, ElementRef, OnDestroy, OnInit, Renderer2, ViewChild } from '@angular/core';
import { CurrencyPipe, NgFor, NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { Subscription, combineLatest } from 'rxjs';
import { Vehicle } from '../../core/models/portal.models';
import { PortalApiService } from '../../core/services/portal-api.service';

@Component({
  selector: 'dp-inventory-list',
  standalone: true,
  imports: [CurrencyPipe, FormsModule, NgFor, NgIf, RouterLink],
  template: `
    <div class="page">
      <h1>Inventory</h1>
      <form class="search" (ngSubmit)="search()">
        <input name="q" type="search" placeholder="Search by VIN or model" [(ngModel)]="searchText">
        <button type="submit">Search</button>
      </form>
      <p class="summary" data-testid="search-summary" #summary [hidden]="!query"></p>
      <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
      <table class="grid" *ngIf="vehicles.length; else empty">
        <thead>
          <tr><th>VIN</th><th>Model</th><th>Year</th><th>Status</th><th>Price</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let v of vehicles" data-testid="vehicle-row">
            <td><a [routerLink]="['/inventory', v.vin]">{{ v.vin }}</a></td>
            <td>{{ v.model }}</td>
            <td>{{ v.year }}</td>
            <td><span class="badge" [class]="v.status">{{ v.status }}</span></td>
            <td>{{ v.priceCents / 100 | currency: 'USD' }}</td>
          </tr>
        </tbody>
      </table>
      <ng-template #empty><p class="muted" *ngIf="!loading">No vehicles to show.</p></ng-template>
    </div>
  `,
  styles: [`
    .search { display: flex; gap: 8px; margin-bottom: 12px; }
    .search input { flex: 1; }
  `],
})
export class InventoryListComponent implements OnInit, OnDestroy {
  @ViewChild('summary', { static: true }) summary!: ElementRef<HTMLElement>;

  vehicles: Vehicle[] = [];
  query = '';
  searchText = '';
  loading = true;
  errorMessage = '';
  private subscription?: Subscription;

  constructor(
    private api: PortalApiService,
    private route: ActivatedRoute,
    private router: Router,
    private renderer: Renderer2,
  ) {}

  ngOnInit(): void {
    this.subscription = combineLatest([this.api.inventory(), this.route.queryParamMap]).subscribe({
      next: ([inventory, params]) => {
        this.loading = false;
        this.query = (params.get('q') ?? '').trim();
        this.searchText = this.query;
        this.vehicles = this.filter(inventory, this.query);
        this.renderSummary();
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'Inventory is unavailable right now.';
      },
    });
  }

  ngOnDestroy(): void {
    this.subscription?.unsubscribe();
  }

  search(): void {
    const q = this.searchText.trim();
    this.router.navigate([], { relativeTo: this.route, queryParams: { q: q || null } });
  }

  private filter(inventory: Vehicle[], query: string): Vehicle[] {
    const needle = query.toLowerCase();
    if (!needle) {
      return inventory;
    }
    return inventory.filter(v => v.vin.toLowerCase().includes(needle) || v.model.toLowerCase().includes(needle));
  }

  private renderSummary(): void {
    const count = this.vehicles.length;
    const label = count === 1 ? 'vehicle matches' : 'vehicles match';
    this.renderer.setProperty(
      this.summary.nativeElement,
      'innerHTML',
      this.query ? `${count} ${label} <strong>${this.query}</strong>` : '',
    );
  }
}
