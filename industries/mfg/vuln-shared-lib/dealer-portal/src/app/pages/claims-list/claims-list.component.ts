import { Component, OnInit } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { RouterLink } from '@angular/router';
import { WarrantyClaim } from '../../core/models/portal.models';
import { PortalDatePipe } from '../../core/pipes/portal-date.pipe';
import { PortalApiService } from '../../core/services/portal-api.service';

@Component({
  selector: 'dp-claims-list',
  standalone: true,
  imports: [NgFor, NgIf, PortalDatePipe, RouterLink],
  template: `
    <div class="page">
      <div class="heading">
        <h1>Warranty claims</h1>
        <a routerLink="/claims/new" class="new-claim">Submit a claim</a>
      </div>
      <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
      <table class="grid" *ngIf="claims.length; else empty">
        <thead>
          <tr><th>Claim</th><th>VIN</th><th>Status</th><th>Description</th><th>Submitted</th></tr>
        </thead>
        <tbody>
          <tr *ngFor="let c of claims" data-testid="claim-row">
            <td>{{ c.id }}</td>
            <td><a [routerLink]="['/inventory', c.vin]">{{ c.vin }}</a></td>
            <td><span class="badge" [class]="c.status">{{ c.status }}</span></td>
            <td class="description">{{ c.description }}</td>
            <td [title]="c.submittedAt | portalDate: 'datetime'">{{ c.submittedAt | portalDate: 'relative' }}</td>
          </tr>
        </tbody>
      </table>
      <ng-template #empty><p class="muted" *ngIf="!loading">No warranty claims yet.</p></ng-template>
    </div>
  `,
  styles: [`
    .heading { display: flex; justify-content: space-between; align-items: baseline; }
    .description { max-width: 420px; white-space: pre-line; }
  `],
})
export class ClaimsListComponent implements OnInit {
  claims: WarrantyClaim[] = [];
  loading = true;
  errorMessage = '';

  constructor(private api: PortalApiService) {}

  ngOnInit(): void {
    this.api.claims().subscribe({
      next: claims => {
        this.loading = false;
        this.claims = claims
          .slice()
          .sort((a, b) => b.submittedAt.localeCompare(a.submittedAt));
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'Warranty claims are unavailable right now.';
      },
    });
  }

}
