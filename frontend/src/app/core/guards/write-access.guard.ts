import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { catchError, map, of } from 'rxjs';
import { PapelUsuario } from '../models/enums';
import { AuthService } from '../services/auth.service';

export const writeAccessGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  const canWrite = (papel: PapelUsuario): boolean =>
    papel === PapelUsuario.ADMIN || papel === PapelUsuario.ANALISTA;
  const usuario = auth.usuario();
  if (usuario) return canWrite(usuario.papel) || router.createUrlTree(['/dashboard']);

  return auth.carregarPerfil().pipe(
    map((loadedUser) =>
      canWrite(loadedUser.papel) ? true : router.createUrlTree(['/dashboard'])
    ),
    catchError(() => of(router.createUrlTree(['/login'])))
  );
};
