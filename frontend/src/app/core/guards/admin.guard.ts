import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { PapelUsuario } from '../models/enums';
import { AuthService } from '../services/auth.service';

export const adminGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const usuario = auth.usuario();
  if (usuario?.papel === PapelUsuario.ADMIN) {
    return true;
  }

  if (!usuario) {
    return auth.carregarPerfil().pipe(
      map((u) => (u.papel === PapelUsuario.ADMIN ? true : router.createUrlTree(['/dashboard']))),
      catchError(() => of(router.createUrlTree(['/login'])))
    );
  }

  return router.createUrlTree(['/dashboard']);
};
