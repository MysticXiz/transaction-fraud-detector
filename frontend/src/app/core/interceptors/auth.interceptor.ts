import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';
import { AuthService } from '../services/auth.service';

/**
 * Envia a sessão nas chamadas da API e sinaliza requisições feitas pelo aplicativo.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (!req.url.startsWith('/api/')) return next(req);

  const clonado = req.clone({
    withCredentials: true,
    setHeaders: { 'X-Requested-With': 'XMLHttpRequest' },
  });

  return next(clonado).pipe(
    catchError((err: HttpErrorResponse) => {
      if (err.status === 401 && !req.url.endsWith('/auth/session')) {
        const sessaoAtiva = auth.estaAutenticado();
        auth.clearSession();
        // The guard owns redirects while restoring a session, before a profile is loaded.
        if (sessaoAtiva) {
          void router.navigate(['/login'], { queryParams: { returnUrl: router.url }, replaceUrl: true });
        }
      }
      return throwError(() => err);
    })
  );
};
