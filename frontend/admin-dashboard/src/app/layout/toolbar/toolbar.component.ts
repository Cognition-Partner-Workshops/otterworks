import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatIconModule } from '@angular/material/icon';
import { MatButtonModule } from '@angular/material/button';
import { MatMenuModule } from '@angular/material/menu';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-toolbar',
  standalone: true,
  imports: [CommonModule, MatToolbarModule, MatIconModule, MatButtonModule, MatMenuModule],
  template: `
    <mat-toolbar class="app-toolbar">
      <div class="toolbar-brand">
        <img src="assets/bank-mark.svg" alt="Document Center logo" width="28" height="28" />
        <span class="brand-name">BANK OF AMERICA</span>
        <span aria-hidden="true" class="brand-divider"></span>
        <span class="product-name">Document Center</span>
      </div>
      <span class="spacer"></span>
      <span class="user-info" *ngIf="authService.currentUser as user">
        <mat-icon>account_circle</mat-icon>
        <span class="user-name">{{ user.displayName }}</span>
      </span>
      <button mat-icon-button [matMenuTriggerFor]="userMenu" aria-label="User menu">
        <mat-icon>more_vert</mat-icon>
      </button>
      <mat-menu #userMenu="matMenu">
        <button mat-menu-item (click)="authService.logout()">
          <mat-icon>logout</mat-icon>
          <span>Logout</span>
        </button>
      </mat-menu>
    </mat-toolbar>
  `,
  styles: [`
    .app-toolbar {
      background: #ffffff;
      color: #012169;
      border-bottom: 1px solid #dddddd;
      height: 64px;
      box-shadow: none;
    }

    .toolbar-brand {
      display: flex;
      align-items: center;
      gap: 12px;
      white-space: nowrap;
    }

    .toolbar-brand img {
      flex: 0 0 auto;
    }

    .brand-name {
      color: #012169;
      font-size: 0.9rem;
      font-weight: 700;
      letter-spacing: 0.16em;
    }

    .brand-divider {
      width: 1px;
      height: 20px;
      background: #dddddd;
    }

    .product-name {
      color: #666666;
      font-size: 0.9rem;
      font-weight: 400;
    }

    .spacer {
      flex: 1;
    }

    .user-info {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-right: 8px;
      color: #666666;
    }

    .user-name {
      font-size: 0.9rem;
    }
  `],
})
export class ToolbarComponent {
  constructor(public authService: AuthService) {}
}
