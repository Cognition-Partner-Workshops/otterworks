import { Component, OnInit } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { PortalApiService } from '../../core/services/portal-api.service';

export const VIN_PATTERN = '^[A-HJ-NPR-Z0-9]{17}$';

@Component({
  selector: 'dp-claim-submit',
  standalone: true,
  imports: [FormsModule, NgIf, RouterLink],
  template: `
    <div class="page">
      <a routerLink="/claims">&larr; Back to claims</a>
      <form class="card" (ngSubmit)="onSubmit()" #form="ngForm">
        <h1>Submit a warranty claim</h1>
        <label for="vin">VIN</label>
        <input id="vin" name="vin" required [pattern]="vinPattern" maxlength="17" [(ngModel)]="vin">
        <label for="description">What went wrong?</label>
        <textarea id="description" name="description" rows="6" required maxlength="2000"
                  [(ngModel)]="description"></textarea>
        <p class="error" *ngIf="errorMessage" role="alert">{{ errorMessage }}</p>
        <button type="submit" [disabled]="submitting || !form.valid">Submit claim</button>
      </form>
    </div>
  `,
  styles: [`button { margin-top: 16px; }`],
})
export class ClaimSubmitComponent implements OnInit {
  readonly vinPattern = VIN_PATTERN;
  vin = '';
  description = '';
  submitting = false;
  errorMessage = '';

  constructor(private api: PortalApiService, private route: ActivatedRoute, private router: Router) {}

  ngOnInit(): void {
    this.vin = this.route.snapshot.queryParamMap.get('vin') ?? '';
  }

  onSubmit(): void {
    const vin = this.vin.trim().toUpperCase();
    const description = this.description.trim();
    if (!new RegExp(VIN_PATTERN).test(vin) || !description) {
      this.errorMessage = 'Enter a 17-character VIN and a description.';
      return;
    }
    this.submitting = true;
    this.errorMessage = '';
    this.api.submitClaim({ vin, description }).subscribe({
      next: () => {
        this.submitting = false;
        this.router.navigate(['/claims']);
      },
      error: () => {
        this.submitting = false;
        this.errorMessage = 'The claim could not be submitted. Try again later.';
      },
    });
  }
}
