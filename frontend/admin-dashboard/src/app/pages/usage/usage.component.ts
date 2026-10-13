import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClient } from '@angular/common/http';
import { forkJoin } from 'rxjs';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';
import { MatSelectModule } from '@angular/material/select';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

/** report-service /api/v1/reports/ubw/{report} response. */
export interface UbwReport {
  report: string;
  backend: 'sqlserver' | 'snowflake';
  source: string;
  parameters: Record<string, string>;
  fields: string[];
  rowCount: number;
  rows: Record<string, any>[];
}

/**
 * Usage & Billing Warehouse usage page: the tenant usage mart and the plan seat summary, read
 * through report-service, which UBW_BACKEND points at SQL Server or Snowflake.
 */
@Component({
  selector: 'app-usage',
  standalone: true,
  imports: [
    CommonModule, FormsModule, MatCardModule, MatTableModule, MatChipsModule, MatIconModule,
    MatSelectModule, MatFormFieldModule, MatProgressSpinnerModule,
  ],
  template: `
    <div class="page-container">
      <div class="header">
        <h1 class="page-title">Tenant Usage</h1>
        <mat-form-field appearance="outline" class="date-field">
          <mat-label>Business date</mat-label>
          <mat-select [(ngModel)]="businessDate" (selectionChange)="load()">
            <mat-option *ngFor="let d of businessDates" [value]="d">{{ d }}</mat-option>
          </mat-select>
        </mat-form-field>
      </div>

      <div *ngIf="usage" class="backend" data-testid="ubw-backend">
        <mat-icon>{{ usage.backend === 'snowflake' ? 'ac_unit' : 'dns' }}</mat-icon>
        Warehouse: <strong>{{ usage.backend === 'snowflake' ? 'Snowflake' : 'SQL Server' }}</strong>
        <span class="sources">reading {{ usage.source }} and {{ seats?.source }}</span>
      </div>

      <div *ngIf="error" class="error">{{ error }}</div>
      <div *ngIf="loading" class="loading-container"><mat-spinner diameter="40"></mat-spinner></div>

      <ng-container *ngIf="!loading && usage && seats">
        <div class="totals">
          <mat-card class="total"><div class="label">Tenants</div><div class="value">{{ usage.rowCount }}</div></mat-card>
          <mat-card class="total"><div class="label">API units</div><div class="value">{{ sum(usage.rows, 'api_units') | number }}</div></mat-card>
          <mat-card class="total"><div class="label">Compute units</div><div class="value">{{ sum(usage.rows, 'compute_units') | number }}</div></mat-card>
          <mat-card class="total"><div class="label">Storage peak (MB)</div><div class="value">{{ sum(usage.rows, 'storage_peak_mb') | number }}</div></mat-card>
          <mat-card class="total"><div class="label">Seats</div><div class="value">{{ sum(seats.rows, 'seat_count') | number }}</div></mat-card>
        </div>

        <mat-card class="section">
          <mat-card-header><mat-card-title>Plan seat summary</mat-card-title></mat-card-header>
          <table mat-table [dataSource]="seats.rows" class="full-width">
            <ng-container *ngFor="let c of seatColumns" [matColumnDef]="c">
              <th mat-header-cell *matHeaderCellDef>{{ c }}</th>
              <td mat-cell *matCellDef="let row">{{ row[c] }}</td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="seatColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: seatColumns"></tr>
          </table>
        </mat-card>

        <mat-card class="section">
          <mat-card-header><mat-card-title>Tenant usage (top 12 by storage)</mat-card-title></mat-card-header>
          <table mat-table [dataSource]="topTenants()" class="full-width">
            <ng-container *ngFor="let c of usageColumns" [matColumnDef]="c">
              <th mat-header-cell *matHeaderCellDef>{{ c }}</th>
              <td mat-cell *matCellDef="let row">{{ row[c] }}</td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="usageColumns"></tr>
            <tr mat-row *matRowDef="let row; columns: usageColumns"></tr>
          </table>
        </mat-card>
      </ng-container>
    </div>
  `,
  styles: [`
    .header { display: flex; align-items: center; justify-content: space-between; }
    .date-field { width: 180px; }
    .backend { display: flex; align-items: center; gap: 8px; margin-bottom: 16px; font-size: 15px; }
    .sources { color: rgba(0,0,0,.55); font-family: monospace; font-size: 13px; margin-left: 8px; }
    .totals { display: grid; grid-template-columns: repeat(5, 1fr); gap: 12px; margin-bottom: 16px; }
    .total { padding: 12px 16px; }
    .label { font-size: 12px; color: rgba(0,0,0,.6); }
    .value { font-size: 22px; font-weight: 600; }
    .section { margin-bottom: 16px; }
    .full-width { width: 100%; }
    .error { color: #b3261e; margin-bottom: 12px; }
    .loading-container { display: flex; justify-content: center; padding: 48px; }
  `],
})
export class UsageComponent implements OnInit {
  readonly businessDates = ['2026-09-30', '2026-09-15'];
  readonly seatColumns = ['plan_tier', 'tenant_count', 'seat_count', 'seat_limit_total'];
  readonly usageColumns = ['tenant_name', 'plan_tier', 'region_code', 'api_units', 'compute_units', 'storage_peak_mb', 'active_users'];
  businessDate = this.businessDates[0];
  usage?: UbwReport;
  seats?: UbwReport;
  loading = false;
  error = '';

  constructor(private http: HttpClient) {}

  ngOnInit(): void {
    this.load();
  }

  load(): void {
    this.loading = true;
    this.error = '';
    const params = { businessDate: this.businessDate };
    forkJoin({
      usage: this.http.get<UbwReport>('/api/v1/reports/ubw/rpt_tenant_usage_daily', { params }),
      seats: this.http.get<UbwReport>('/api/v1/reports/ubw/rpt_plan_mix', { params }),
    }).subscribe({
      next: ({ usage, seats }) => {
        this.usage = usage;
        this.seats = seats;
        this.loading = false;
      },
      error: err => {
        this.error = `Could not load the usage reports: ${err.status || ''} ${err.message || err}`;
        this.loading = false;
      },
    });
  }

  sum(rows: Record<string, any>[], column: string): number {
    return rows.reduce((total, row) => total + Number(row[column] || 0), 0);
  }

  topTenants(): Record<string, any>[] {
    return [...(this.usage?.rows || [])]
      .sort((a, b) => Number(b['storage_peak_mb']) - Number(a['storage_peak_mb']))
      .slice(0, 12);
  }
}
