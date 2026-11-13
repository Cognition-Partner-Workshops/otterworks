import { Routes } from '@angular/router';
import { authGuard } from './core/guards/auth.guard';

export const routes: Routes = [
  {
    path: 'sign-in',
    loadComponent: () => import('./pages/sign-in/sign-in.component').then(m => m.SignInComponent),
  },
  {
    path: '',
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'inventory' },
      {
        path: 'inventory',
        loadComponent: () =>
          import('./pages/inventory-list/inventory-list.component').then(m => m.InventoryListComponent),
      },
      {
        path: 'inventory/:vin',
        loadComponent: () =>
          import('./pages/inventory-detail/inventory-detail.component').then(m => m.InventoryDetailComponent),
      },
      {
        path: 'claims',
        loadComponent: () => import('./pages/claims-list/claims-list.component').then(m => m.ClaimsListComponent),
      },
      {
        path: 'claims/new',
        loadComponent: () => import('./pages/claim-submit/claim-submit.component').then(m => m.ClaimSubmitComponent),
      },
      {
        path: 'notices',
        loadComponent: () => import('./pages/notices/notices.component').then(m => m.NoticesComponent),
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
