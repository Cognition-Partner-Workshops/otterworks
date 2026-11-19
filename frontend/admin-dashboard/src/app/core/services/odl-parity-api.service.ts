import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable, switchMap } from 'rxjs';
import { OdlException, OdlPage, ParityReport, ParityRun } from '../models/odl-parity.model';

@Injectable({ providedIn: 'root' })
export class OdlParityApiService {
  private readonly baseUrl = '/api/v1/odl';

  constructor(private http: HttpClient) {}

  listRuns(): Observable<{ items: ParityRun[] }> {
    return this.http.get<{ items: ParityRun[] }>(`${this.baseUrl}/parity`);
  }

  getReport(runId: string): Observable<ParityReport> {
    if (runId === 'latest') {
      return this.http.get<ParityRun>(`${this.baseUrl}/parity/latest`).pipe(
        switchMap(run => this.getReport(run.run_id)),
      );
    }
    return this.http.get<ParityReport>(`${this.baseUrl}/parity/${encodeURIComponent(runId)}`);
  }

  getReportFile(runId: string): Observable<Blob> {
    return this.http.get(`${this.baseUrl}/parity/${encodeURIComponent(runId)}.csv`, { responseType: 'blob' });
  }

  listExceptions(reason: string, cursor?: string): Observable<OdlPage<OdlException>> {
    let params = new HttpParams().set('limit', 20);
    if (reason) params = params.set('reason', reason);
    if (cursor) params = params.set('cursor', cursor);
    return this.http.get<OdlPage<OdlException>>(`${this.baseUrl}/exceptions`, { params });
  }
}
