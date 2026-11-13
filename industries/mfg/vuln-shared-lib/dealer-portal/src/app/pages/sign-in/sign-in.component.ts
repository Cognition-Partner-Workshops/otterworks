import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'dp-sign-in',
  standalone: true,
  imports: [FormsModule, NgIf],
  template: `
    <div class="page sign-in">
      <form class="card" (ngSubmit)="onSubmit()" #form="ngForm">
        <h1>Dealer Portal</h1>
        <p class="muted">Sign in with your dealer account.</p>
        <label for="email">Email</label>
        <input id="email" name="email" type="email" required [(ngModel)]="email" autocomplete="username">
        <label for="password">Password</label>
        <input id="password" name="password" type="password" required [(ngModel)]="password"
               autocomplete="current-password">
        <p class="error" *ngIf="errorMessage" role="alert">{{ errorMessage }}</p>
        <button type="submit" [disabled]="loading || !form.valid">{{ loading ? 'Signing in…' : 'Sign in' }}</button>
      </form>
    </div>
  `,
  styles: [`
    .sign-in { max-width: 420px; padding-top: 80px; }
    button { margin-top: 16px; width: 100%; }
  `],
})
export class SignInComponent {
  email = '';
  password = '';
  loading = false;
  errorMessage = '';

  constructor(private auth: AuthService, private router: Router, private route: ActivatedRoute) {}

  onSubmit(): void {
    if (!this.email || !this.password) {
      return;
    }
    this.loading = true;
    this.errorMessage = '';
    this.auth.signIn(this.email, this.password).subscribe({
      next: () => {
        this.loading = false;
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
        this.router.navigateByUrl(returnUrl && returnUrl.startsWith('/') ? returnUrl : '/inventory');
      },
      error: () => {
        this.loading = false;
        this.errorMessage = 'Sign-in failed. Check your email and password.';
      },
    });
  }
}
