import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { LoginRequest, LoginResponse, RegisterRequest, Usuario } from '../models/usuario.model';

const TOKEN_KEY = 'df_access_token';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = `${environment.apiUrl}/auth`;

  /** Usuário autenticado, carregado via GET /auth/me após login/refresh de página. */
  usuario = signal<Usuario | null>(null);
  estaAutenticado = computed(() => !!this.token());

  token(): string | null {
    return localStorage.getItem(TOKEN_KEY);
  }

  login(payload: LoginRequest) {
    return this.http.post<LoginResponse>(`${this.baseUrl}/login`, payload).pipe(
      tap((resp) => {
        localStorage.setItem(TOKEN_KEY, resp.access_token);
      })
    );
  }

  registrar(payload: RegisterRequest) {
    return this.http.post<Usuario>(`${this.baseUrl}/register`, payload);
  }

  carregarPerfil() {
    return this.http.get<Usuario>(`${this.baseUrl}/me`).pipe(tap((u) => this.usuario.set(u)));
  }

  logout(): void {
    localStorage.removeItem(TOKEN_KEY);
    this.usuario.set(null);
    this.router.navigateByUrl('/login');
  }
}
