import { Component, ElementRef, OnDestroy, OnInit, ViewChild } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';
import { EMPTY, Subject, Subscription, catchError, switchMap, takeUntil, tap } from 'rxjs';
import { OdlParityApiService } from '../../core/services/odl-parity-api.service';
import { OdlException, ParityReport, ParityRun, ParityTable } from '../../core/models/odl-parity.model';

@Component({
  selector: 'app-odl-parity',
  standalone: true,
  imports: [CommonModule, FormsModule, MatCardModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatProgressSpinnerModule],
  template: `
    <div class="page-container">
      <div class="page-header">
        <div><h1 class="page-title">ODL Parity</h1>
          <p class="page-subtitle">Independent source-to-Mongo verification at four depths</p></div>
        <button mat-raised-button color="primary" (click)="downloadCsv()" [disabled]="!report || loading || downloading">
          <mat-icon>download</mat-icon> Download CSV
        </button>
      </div>
      <mat-card><mat-card-content>
        <form class="filters" (ngSubmit)="loadRun()">
          <mat-form-field class="run-field" appearance="outline"><mat-label>Run ID</mat-label>
            <input matInput name="runId" [(ngModel)]="runIdInput" placeholder="latest" />
          </mat-form-field>
          <mat-form-field class="run-field" appearance="outline" *ngIf="runs.length"><mat-label>Known runs</mat-label>
            <mat-select name="knownRun" [(ngModel)]="runIdInput">
              <mat-option value="latest">Latest</mat-option>
              <mat-option *ngFor="let run of runs" [value]="run.run_id">{{ run.run_id }} · {{ run.passed ? 'PASS' : 'FAIL' }}</mat-option>
            </mat-select>
          </mat-form-field>
          <button mat-raised-button color="primary" type="submit" [disabled]="loading">Load</button>
        </form>
        <p *ngIf="runsError" role="alert">{{ runsError }}</p>
      </mat-card-content></mat-card>
      <div class="loading" *ngIf="loading"><mat-spinner diameter="36"></mat-spinner></div>
      <p class="notice" *ngIf="error" role="alert">{{ error }}</p>
      <ng-container *ngIf="report && !loading">
        <div class="status-row">
          <strong class="badge" [class.fail]="!report.passed">{{ report.passed ? 'PASS' : 'FAIL' }}</strong>
          <span>Run <code>{{ report.run_id }}</code></span><span>Generated {{ report.generated_at | date:'medium':'UTC' }} UTC</span>
        </div>
        <mat-card><mat-card-header><mat-card-title>Source × table parity</mat-card-title></mat-card-header>
          <mat-card-content class="table-scroll">
            <table class="grid" aria-label="Per-table parity depths">
              <thead><tr><th>Source</th><th>Table</th><th>Count</th><th>Column profiles</th><th>Keyed hashes</th><th>Sampled values</th></tr></thead>
              <tbody><tr *ngFor="let row of rows">
                <td>{{ row.source }}</td><td><strong>{{ row.name }}</strong></td>
                <td><strong [class.fail]="!row.depths.count.passed">{{ verdict(row.depths.count.passed) }}</strong>
                  <div>Source {{ row.depths.count.source | number }} / target {{ row.depths.count.placed | number }}</div>
                  <div>Unplaced {{ row.depths.count.unplaced | number }}</div></td>
                <td><strong [class.fail]="!row.depths.profile.passed">{{ verdict(row.depths.profile.passed) }}</strong>
                  <div>Fields checked {{ row.profileChecked | number }}</div><div>Fields failed {{ row.profileFailed | number }}</div></td>
                <td><strong [class.fail]="!row.depths.keyed_hash.passed">{{ verdict(row.depths.keyed_hash.passed) }}</strong>
                  <div>Matched {{ row.depths.keyed_hash.matched | number }} / mismatched {{ row.depths.keyed_hash.mismatched | number }}</div>
                  <div>Missing {{ row.depths.keyed_hash.missing_in_target | number }} / extra {{ row.depths.keyed_hash.extra_in_target | number }}</div></td>
                <td><strong [class.fail]="!row.depths.sampled_values.passed">{{ verdict(row.depths.sampled_values.passed) }}</strong>
                  <div>Rows {{ row.depths.sampled_values.size | number }} / fields {{ row.depths.sampled_values.fields_compared | number }}</div>
                  <div>Differences {{ row.depths.sampled_values.difference_count | number }}</div></td>
              </tr></tbody>
            </table>
            <p *ngIf="!rows.length">No table results in this run.</p>
          </mat-card-content>
        </mat-card>
        <mat-card><mat-card-header><mat-card-title>Exception summary at audit time</mat-card-title></mat-card-header>
          <mat-card-content>
            <ul><li *ngFor="let reason of report.exception_summary | keyvalue">{{ reason.key }}: {{ reason.value | number }}</li></ul>
            <p *ngIf="!reasons.length">No exceptions recorded in this audit.</p>
          </mat-card-content>
        </mat-card>
        <mat-card><mat-card-header><mat-card-title>Live exceptions</mat-card-title>
          <mat-card-subtitle>Current mapping exceptions; these may change after the selected audit.</mat-card-subtitle></mat-card-header>
          <mat-card-content>
            <mat-form-field appearance="outline"><mat-label>Reason</mat-label>
              <mat-select [(ngModel)]="reasonFilter" (selectionChange)="resetExceptions()">
                <mat-option value="">All reasons</mat-option>
                <mat-option *ngFor="let reason of reasons" [value]="reason">{{ reason }}</mat-option>
              </mat-select>
            </mat-form-field>
            <p *ngIf="exceptionsError" role="alert">{{ exceptionsError }}</p>
            <div #exceptionsTable class="table-scroll exceptions-results" [style.min-height.px]="exceptionsMinHeight" [attr.aria-busy]="exceptionsLoading">
              <mat-spinner class="exceptions-spinner" *ngIf="exceptionsLoading" diameter="24"></mat-spinner>
              <table class="grid" aria-label="Mapping exceptions"><thead><tr><th>Exception</th><th>Reason</th><th>Status</th><th>Source keys</th></tr></thead>
                <tbody><tr *ngFor="let item of exceptions"><td><code>{{ item._id }}</code></td><td>{{ item.reason }}</td><td>{{ item.status }}</td><td>{{ item.source_keys.join(', ') }}</td></tr></tbody>
              </table>
              <p *ngIf="!exceptions.length && !exceptionsError && !exceptionsLoading">No exceptions found.</p>
            </div>
            <div class="pagination">
              <button mat-stroked-button (click)="previousExceptions()" [disabled]="!previousCursors.length || exceptionsLoading">Previous</button>
              <span>Page {{ previousCursors.length + 1 }}</span>
              <button mat-stroked-button (click)="nextExceptions()" [disabled]="!nextCursor || exceptionsLoading">Next</button>
            </div>
          </mat-card-content>
        </mat-card>
      </ng-container>
    </div>
  `,
  styles: [`
    mat-card { margin-bottom: 20px; }
    .filters, .status-row, .pagination { display: flex; flex-wrap: wrap; align-items: center; gap: 16px; }
    .filters { padding-top: 12px; }
    .run-field { width: 36rem; max-width: 100%; }
    .exceptions-results { position: relative; }
    .exceptions-spinner { position: absolute; top: 8px; right: 8px; }
    .status-row { margin: 20px 0; }
    .badge { padding: 6px 12px; background: #e8f5e9; color: #1b5e20; border-radius: 4px; }
    .fail, .notice { color: #b71c1c; }
    .badge.fail { background: #ffebee; }
    .loading { display: flex; justify-content: center; padding: 32px; }
    .table-scroll { overflow-x: auto; }
    .grid { width: 100%; border-collapse: collapse; margin: 16px 0; }
    .grid th, .grid td { text-align: left; vertical-align: top; border-bottom: 1px solid #ddd; padding: 12px; }
    .grid td div { margin-top: 6px; white-space: nowrap; }
    .pagination { margin-top: 16px; }
  `],
})
export class OdlParityComponent implements OnInit, OnDestroy {
  runIdInput = 'latest';
  runs: ParityRun[] = [];
  report: ParityReport | null = null;
  rows: (ParityTable & { name: string; profileChecked: number; profileFailed: number })[] = [];
  loading = false;
  downloading = false;
  error = '';
  runsError = '';
  exceptionsError = '';
  exceptionsLoading = false;
  exceptionsMinHeight = 0;
  @ViewChild('exceptionsTable') private exceptionsTable?: ElementRef<HTMLElement>;
  exceptions: OdlException[] = [];
  reasonFilter = '';
  nextCursor: string | null = null;
  previousCursors: string[] = [];
  private currentCursor = '';
  private readonly load$ = new Subject<string>();
  private readonly destroy$ = new Subject<void>();
  private exceptionsRequest?: Subscription;

  constructor(private api: OdlParityApiService) {}

  get reasons(): string[] { return Object.keys(this.report?.exception_summary || {}).sort(); }
  verdict(passed: boolean): string { return passed ? 'PASS' : 'FAIL'; }

  ngOnInit(): void {
    this.api.listRuns().pipe(takeUntil(this.destroy$)).subscribe({
      next: result => this.runs = result.items,
      error: () => this.runsError = 'Could not list runs. You can still load a run ID.',
    });
    this.load$.pipe(
      tap(() => { this.loading = true; this.error = ''; this.report = null; this.exceptionsRequest?.unsubscribe(); }),
      switchMap(id => this.api.getReport(id).pipe(catchError((err: HttpErrorResponse) => {
        this.loading = false;
        this.error = err.status === 404 ? 'No parity report found for this run.' : `Could not load parity report (${err.status}).`;
        return EMPTY;
      }))), takeUntil(this.destroy$),
    ).subscribe(report => {
      this.report = report;
      this.runIdInput = report.run_id;
      this.rows = Object.entries(report.tables).map(([name, table]) => {
        const fields = Object.values(table.depths.profile.fields);
        return { ...table, name, profileChecked: fields.length,
          profileFailed: fields.filter(checks => Object.values(checks).some(check => !check.passed)).length };
      });
      this.loading = false;
      this.reasonFilter = '';
      this.resetExceptions();
    });
    this.loadRun();
  }

  loadRun(): void { this.load$.next(this.runIdInput.trim() || 'latest'); }

  resetExceptions(): void {
    this.previousCursors = [];
    this.currentCursor = '';
    this.nextCursor = null;
    this.exceptions = [];
    this.exceptionsMinHeight = 0;
    this.fetchExceptions('');
  }

  nextExceptions(): void {
    if (!this.nextCursor || this.exceptionsLoading) return;
    this.fetchExceptions(this.nextCursor, [...this.previousCursors, this.currentCursor]);
  }

  previousExceptions(): void {
    if (this.exceptionsLoading) return;
    const cursor = this.previousCursors[this.previousCursors.length - 1];
    if (cursor !== undefined) this.fetchExceptions(cursor, this.previousCursors.slice(0, -1));
  }

  private fetchExceptions(cursor: string, history = this.previousCursors): void {
    this.exceptionsRequest?.unsubscribe();
    this.exceptionsMinHeight = Math.max(this.exceptionsMinHeight, this.exceptionsTable?.nativeElement.offsetHeight || 0);
    this.exceptionsLoading = true;
    this.exceptionsError = '';
    this.exceptionsRequest = this.api.listExceptions(this.reasonFilter, cursor).pipe(takeUntil(this.destroy$)).subscribe({
      next: result => {
        this.exceptions = result.items;
        this.nextCursor = result.next_cursor;
        this.currentCursor = cursor;
        this.previousCursors = history;
        this.exceptionsLoading = false;
      },
      error: () => { this.exceptionsLoading = false; this.exceptionsError = 'Could not load exceptions. Select a reason to retry.'; },
    });
  }

  downloadCsv(): void {
    if (!this.report || this.downloading) return;
    const runId = this.report.run_id;
    this.downloading = true;
    this.api.getReportFile(runId).pipe(takeUntil(this.destroy$)).subscribe({
      next: blob => {
        this.downloading = false;
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = `odl-parity-${runId}.csv`;
        anchor.click();
        setTimeout(() => URL.revokeObjectURL(url), 60_000);
      },
      error: () => { this.downloading = false; this.error = 'CSV download failed. Please retry.'; },
    });
  }

  ngOnDestroy(): void {
    this.destroy$.next();
    this.destroy$.complete();
    this.exceptionsRequest?.unsubscribe();
  }
}
