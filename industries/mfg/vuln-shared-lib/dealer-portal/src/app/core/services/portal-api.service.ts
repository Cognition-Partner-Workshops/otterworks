import { Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { DealerNotice, NewWarrantyClaim, Vehicle, WarrantyClaim } from '../models/portal.models';

@Injectable({ providedIn: 'root' })
export class PortalApiService {
  private readonly base = environment.bffBaseUrl;

  constructor(private http: HttpClient) {}

  inventory(): Observable<Vehicle[]> {
    return this.http.get<Vehicle[]>(`${this.base}/inventory`);
  }

  vehicle(vin: string): Observable<Vehicle> {
    return this.http.get<Vehicle>(`${this.base}/inventory/${encodeURIComponent(vin)}`);
  }

  claims(): Observable<WarrantyClaim[]> {
    return this.http.get<WarrantyClaim[]>(`${this.base}/claims`);
  }

  submitClaim(claim: NewWarrantyClaim): Observable<WarrantyClaim> {
    return this.http.post<WarrantyClaim>(`${this.base}/claims`, claim);
  }

  notices(): Observable<DealerNotice[]> {
    return this.http.get<DealerNotice[]>(`${this.base}/notices`);
  }
}
