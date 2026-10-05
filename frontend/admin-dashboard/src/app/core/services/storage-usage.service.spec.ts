import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { AdminApiService } from './admin-api.service';
import { StorageUsage } from '../models/analytics.model';

describe('AdminApiService storage usage', () => {
  let service: AdminApiService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });
    service = TestBed.inject(AdminApiService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => httpMock.verify());

  it('maps storage usage totals and per-user values', () => {
    let result: StorageUsage | undefined;
    service.getStorageUsage().subscribe(usage => result = usage);

    const request = httpMock.expectOne('/api/v1/admin/storage/usage');
    expect(request.request.method).toBe('GET');
    request.flush({
      total_bytes: 1536,
      file_count: 2,
      users: [
        { user_id: 'user-1', file_count: 2, total_bytes: 1024 },
        { user_id: 'user-2', file_count: 0, total_bytes: 0 },
      ],
    });

    expect(result).toEqual({
      totalBytes: 1536,
      fileCount: 2,
      storageUsed: '1.5 KB',
      byUser: {
        'user-1': { fileCount: 2, totalBytes: 1024 },
        'user-2': { fileCount: 0, totalBytes: 0 },
      },
    });
  });
});
