import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';

export const portalKeyInterceptor: HttpInterceptorFn = (req, next) => {
  if (!req.url.startsWith(environment.bffBaseUrl)) {
    return next(req);
  }

  const auth = inject(AuthService);
  const router = inject(Router);
  const request = req.clone({
    withCredentials: true,
  });

  return next(request).pipe(
    catchError((error: unknown) => {
      const isSessionCall = req.url.startsWith(`${environment.bffBaseUrl}/session`);
      if (error instanceof HttpErrorResponse && error.status === 401 && !isSessionCall) {
        auth.clear();
        router.navigate(['/sign-in'], { queryParams: { returnUrl: router.url } });
      }
      return throwError(() => error);
    }),
  );
};
