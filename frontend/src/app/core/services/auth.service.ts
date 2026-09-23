import { Injectable, computed, inject, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { tap } from 'rxjs';
import { environment } from '../../../environments/environment';
import { LoginRequest, LoginResponse, RegisterRequest, Usuario } from '../models/usuario.model';

@Injectable({ providedIn: 'root' })
export class AuthService {
  private http = inject(HttpClient);
  private router = inject(Router);
  private baseUrl = `${environment.apiUrl}/auth`;

  /** Usuário autenticado, carregado via GET /auth/me após login/refresh de página. */
  usuario = signal<Usuario | null>(null);
  estaAutenticado = computed(() => !!this.usuario());

  token(): string | null {
    return null;
  }

  login(payload: LoginRequest) {
    return this.http.post<LoginResponse>(`${this.baseUrl}/login`, payload, { withCredentials: true }).pipe();
  }

  registrar(payload: RegisterRequest) {
    return this.http.post<Usuario>(`${this.baseUrl}/register`, payload, { withCredentials: true });
  }

  carregarPerfil() {
    return this.http.get<Usuario>(`${this.baseUrl}/me`, { withCredentials: true }).pipe(tap((u) => this.usuario.set(u)));
  }

  logout(): void {
    this.http.post(`${this.baseUrl}/logout`, {}, { withCredentials: true }).subscribe();
    this.usuario.set(null);
    this.router.navigateByUrl('/login');
  }
}
