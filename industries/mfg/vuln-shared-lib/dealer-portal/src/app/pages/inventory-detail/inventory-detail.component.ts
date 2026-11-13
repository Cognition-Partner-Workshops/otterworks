import { Component, Input, OnChanges } from '@angular/core';
import { CurrencyPipe, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { Vehicle } from '../../core/models/portal.models';
import { PortalApiService } from '../../core/services/portal-api.service';

@Component({
  selector: 'dp-inventory-detail',
  standalone: true,
  imports: [CurrencyPipe, NgIf, RouterLink],
  template: `
    <div class="page">
      <a routerLink="/inventory">&larr; Back to inventory</a>
      <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
      <div class="card vehicle" *ngIf="vehicle as v">
        <img [src]="v.imageUrl" [alt]="v.model" width="320">
        <div>
          <h1>{{ v.year }} {{ v.model }}</h1>
          <dl>
            <dt>VIN</dt><dd data-testid="vehicle-vin">{{ v.vin }}</dd>
            <dt>Status</dt><dd><span class="badge" [class]="v.status">{{ v.status }}</span></dd>
            <dt>Price</dt><dd>{{ v.priceCents / 100 | currency: 'USD' }}</dd>
          </dl>
          <a [routerLink]="['/claims/new']" [queryParams]="{ vin: v.vin }">File a warranty claim</a>
        </div>
      </div>
    </div>
  `,
  styles: [`
    .vehicle { display: flex; gap: 24px; margin-top: 16px; }
    img { border-radius: 4px; background: #e6ebf0; }
    dl { display: grid; grid-template-columns: 80px 1fr; gap: 6px; }
    dt { font-weight: 600; }
    dd { margin: 0; }
  `],
})
export class InventoryDetailComponent implements OnChanges {
  @Input() vin = '';

  vehicle: Vehicle | null = null;
  errorMessage = '';

  constructor(private api: PortalApiService) {}

  ngOnChanges(): void {
    this.vehicle = null;
    this.errorMessage = '';
    if (!this.vin) {
      return;
    }
    this.api.vehicle(this.vin).subscribe({
      next: vehicle => (this.vehicle = vehicle),
      error: () => (this.errorMessage = `Vehicle ${this.vin} was not found in your inventory.`),
    });
  }
}
