import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Envia o token bearer nas requisições e redireciona para login em caso de 401.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const token = auth.token();
  const clonado = req.clone({
    withCredentials: true,
    setHeaders: token ? { Authorization: `Bearer ${token}` } : {},
  });

  return next(clonado).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401) {
        auth.logout();
        router.navigateByUrl('/login');
      }
      return throwError(() => err);
    })
  );
};
