import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { NotificationService } from './notification.service';
import {
  LoginRequest,
  RegisterRequest,
  UpdateProfileRequest,
  Usuario,
} from '../models/usuario.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly tokenStorageKey = 'df_access_token';
  private http = inject(HttpClient);
  private router = inject(Router);
  private notifications = inject(NotificationService);
  private baseUrl = `${environment.apiUrl}/auth`;

  /** Usuário autenticado, carregado via GET /auth/me após login/refresh de página. */
  usuario = signal<Usuario | null>(null);
  estaAutenticado = computed(() => !!this.usuario());

  login(payload: LoginRequest) {
    localStorage.removeItem(this.tokenStorageKey);
    return this.http
      .post<void>(`${this.baseUrl}/session`, payload)
      .pipe(tap(() => this.usuario.set(null)));
  }

  registrar(payload: RegisterRequest) {
    return this.http.post<Usuario>(`${this.baseUrl}/register`, payload, { withCredentials: true });
  }

  carregarPerfil() {
    return this.http
      .get<Usuario>(`${this.baseUrl}/me`, { withCredentials: true })
      .pipe(tap((u) => this.usuario.set(u)));
  }

  atualizarPerfil(payload: UpdateProfileRequest) {
    return this.http
      .patch<Usuario>(`${this.baseUrl}/me`, payload, { withCredentials: true })
      .pipe(tap((u) => this.usuario.set(u)));
  }

  logout(): void {
    this.http.post<void>(`${this.baseUrl}/logout`, {}).subscribe({
      next: () => {
        this.clearSession();
        void this.router.navigateByUrl('/login');
      },
      error: () => this.notifications.showError('Não foi possível encerrar a sessão. Tente novamente.'),
    });
  }

  clearSession(): void {
    localStorage.removeItem(this.tokenStorageKey);
    this.usuario.set(null);
  }
}
