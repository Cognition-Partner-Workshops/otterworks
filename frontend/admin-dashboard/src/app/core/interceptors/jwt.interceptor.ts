import { Injectable } from '@angular/core';
import {
  HttpInterceptor,
  HttpRequest,
  HttpHandler,
  HttpEvent,
  HttpErrorResponse,
} from '@angular/common/http';
import { Observable, throwError } from 'rxjs';
import { catchError } from 'rxjs/operators';
import { AuthService } from '../services/auth.service';
import { PEER_REQUEST } from '../services/migration-api.service';
import { MatSnackBar } from '@angular/material/snack-bar';

@Injectable()
export class JwtInterceptor implements HttpInterceptor {
  constructor(private authService: AuthService, private snackBar: MatSnackBar) {}

  intercept(request: HttpRequest<unknown>, next: HttpHandler): Observable<HttpEvent<unknown>> {
    const token = this.authService.getToken();

    if (token) {
      request = request.clone({
        setHeaders: {
          Authorization: `Bearer ${token}`,
        },
      });
    }

    return next.handle(request).pipe(
      catchError((error: HttpErrorResponse) => {
        if (error.status === 401 && !request.context.get(PEER_REQUEST)) {
          this.authService.logout();
        }
        if (error.status === 403 && !request.context.get(PEER_REQUEST) &&
            /^\/api\/v1\/admin(?:\/|\?|$)/.test(request.url)) {
          this.snackBar.open('Access denied: your role does not permit this action', 'Dismiss', {
            duration: 5000,
          });
        }
        return throwError(() => error);
      })
    );
  }
}
