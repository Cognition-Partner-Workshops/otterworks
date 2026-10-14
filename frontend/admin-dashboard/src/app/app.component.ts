import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { SidebarComponent } from './layout/sidebar/sidebar.component';
import { ToolbarComponent } from './layout/toolbar/toolbar.component';
import { AuthService } from './core/services/auth.service';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, RouterOutlet, SidebarComponent, ToolbarComponent],
  template: `
    <div class="app-layout" *ngIf="authService.isAuthenticated; else loginView">
      <app-sidebar [(collapsed)]="sidebarCollapsed"></app-sidebar>
      <div class="main-area">
        <div class="concept-banner">
          Concept demo. Not affiliated with, endorsed by, or produced by Bank of America. All people, figures and events shown are fictional.
        </div>
        <app-toolbar></app-toolbar>
        <main class="content" [class.sidebar-collapsed]="sidebarCollapsed">
          <router-outlet></router-outlet>
        </main>
      </div>
    </div>
    <ng-template #loginView>
      <div class="concept-banner login-banner">
        Concept demo. Not affiliated with, endorsed by, or produced by Bank of America. All people, figures and events shown are fictional.
      </div>
      <router-outlet></router-outlet>
    </ng-template>
  `,
  styles: [`
    .app-layout {
      display: flex;
      min-height: 100vh;
    }

    .main-area {
      flex: 1;
      display: flex;
      flex-direction: column;
      min-width: 0;
    }

    .login-banner {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      z-index: 1000;
    }

    .concept-banner {
      height: 24px;
      display: flex;
      align-items: center;
      justify-content: center;
      padding: 0 8px;
      background: #00123b;
      color: rgba(255, 255, 255, 0.8);
      font-size: 11px;
      text-align: center;
    }

    .content {
      flex: 1;
      padding: 24px;
      background: #f5f5f5;
      overflow-y: auto;
    }
  `],
})
export class AppComponent {
  sidebarCollapsed = false;

  constructor(public authService: AuthService) {}
}
