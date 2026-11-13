import { Component } from '@angular/core';
import { AsyncPipe, NgIf } from '@angular/common';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'dp-root',
  standalone: true,
  imports: [AsyncPipe, NgIf, RouterLink, RouterLinkActive, RouterOutlet],
  template: `
    <header class="topbar" *ngIf="auth.session$ | async as session">
      <span class="brand">Dealer Portal</span>
      <nav>
        <a routerLink="/inventory" routerLinkActive="active">Inventory</a>
        <a routerLink="/claims" routerLinkActive="active">Warranty claims</a>
        <a routerLink="/notices" routerLinkActive="active">Notices</a>
      </nav>
      <span class="who" data-testid="dealer-id">{{ session.dealerId }}</span>
      <button type="button" (click)="signOut()">Sign out</button>
    </header>
    <router-outlet></router-outlet>
  `,
  styles: [`
    .topbar { display: flex; align-items: center; gap: 24px; padding: 12px 24px; background: #12324f; color: #fff; }
    .brand { font-weight: 700; }
    nav { display: flex; gap: 16px; flex: 1; }
    nav a { color: #cfe0f1; text-decoration: none; }
    nav a.active { color: #fff; border-bottom: 2px solid #fff; }
    .who { font-family: monospace; }
    button { background: transparent; border: 1px solid #cfe0f1; }
  `],
})
export class AppComponent {
  constructor(public auth: AuthService, private router: Router) {}

  signOut(): void {
    this.auth.signOut().subscribe(() => this.router.navigate(['/sign-in']));
  }
}
