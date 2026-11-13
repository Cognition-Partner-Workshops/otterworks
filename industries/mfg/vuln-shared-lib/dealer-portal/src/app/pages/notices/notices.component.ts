import { Component, OnInit } from '@angular/core';
import { NgFor, NgIf } from '@angular/common';
import { DealerNotice } from '../../core/models/portal.models';
import { PortalDatePipe } from '../../core/pipes/portal-date.pipe';
import { PortalApiService } from '../../core/services/portal-api.service';

@Component({
  selector: 'dp-notices',
  standalone: true,
  imports: [NgFor, NgIf, PortalDatePipe],
  template: `
    <div class="page">
      <h1>Dealer notices</h1>
      <p class="error" *ngIf="errorMessage">{{ errorMessage }}</p>
      <article class="card" *ngFor="let n of notices" data-testid="notice">
        <header>
          <span class="badge" [class]="n.severity">{{ n.severity }}</span>
          <h2>{{ n.title }}</h2>
          <time [attr.datetime]="n.publishedAt">{{ n.publishedAt | portalDate }}</time>
        </header>
        <p class="body">{{ n.body }}</p>
      </article>
      <p class="muted" *ngIf="!loading && !notices.length && !errorMessage">No notices have been published.</p>
    </div>
  `,
  styles: [`
    header { display: flex; align-items: baseline; gap: 12px; }
    h2 { font-size: 1.1rem; margin: 0; flex: 1; }
    time { color: #5b6b7c; font-size: 0.85rem; }
    .body { white-space: pre-line; }
  `],
})
export class NoticesComponent implements OnInit {
  notices: DealerNotice[] = [];
  loading = true;
  errorMessage = '';

  constructor(private api: PortalApiService) {}

  ngOnInit(): void {
    this.api.notices().subscribe({
      next: notices => {
        this.loading = false;
        this.notices = notices.slice().sort((a, b) => b.publishedAt.localeCompare(a.publishedAt));
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'Dealer notices are unavailable right now.';
      },
    });
  }
}
