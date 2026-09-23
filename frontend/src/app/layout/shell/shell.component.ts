import { Component, OnInit, inject } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive],
  template: `
    <div class="layout">
      <aside class="sidebar">
        <h1 class="titulo">Detecção de Fraude</h1>
        <nav class="nav">
          <a routerLink="/dashboard" routerLinkActive="ativo">Dashboard</a>
          <a routerLink="/datasets" routerLinkActive="ativo">Datasets</a>
          <a routerLink="/benchmark" routerLinkActive="ativo">Benchmark</a>
          <a routerLink="/historico" routerLinkActive="ativo">Histórico</a>
        </nav>

        @if (isAdmin()) {
          <div class="admin-area">
            <button class="admin-btn" type="button" routerLink="/admin/usuarios/novo" routerLinkActive="admin-btn-ativo">
              + Criar usuário
            </button>
          </div>
        }

        <div class="tema-area">
          <button
            class="tema-btn"
            type="button"
            (click)="tema.alternar()"
            [attr.aria-pressed]="tema.escuro()"
          >
            <span class="tema-icone" aria-hidden="true">{{ tema.escuro() ? '☀' : '☾' }}</span>
            {{ tema.escuro() ? 'Modo claro' : 'Modo escuro' }}
          </button>
        </div>

        <div class="rodape">
          @if (auth.usuario(); as u) {
            <p class="usuario-nome">{{ u.nome }}</p>
            <p class="usuario-papel">{{ u.papel }}</p>
          }
          <button class="sair" (click)="auth.logout()">Sair</button>
        </div>
      </aside>
      <main class="conteudo">
        <router-outlet />
      </main>
    </div>
  `,
  styles: [
    `
      .layout {
        display: flex;
        min-height: 100vh;
      }
      .sidebar {
        width: 256px;
        flex-shrink: 0;
        background: var(--cor-sidebar);
        color: #fff;
        display: flex;
        flex-direction: column;
        padding: 24px 0;
      }
      .titulo {
        font-family: 'Trebuchet MS', 'Arial Narrow', sans-serif;
        font-size: 18px;
        font-weight: 800;
        letter-spacing: 0.1em;
        line-height: 1.25;
        text-transform: uppercase;
        padding: 0 24px 24px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 12px;
      }
      .nav {
        display: flex;
        flex-direction: column;
        gap: 2px;
        flex: 1;
      }
      .nav a {
        padding: 12px 24px;
        color: #cbd5e1;
        font-weight: 500;
        font-size: 14.5px;
      }
      .nav a:hover { background: rgba(255, 255, 255, 0.06); color: #fff; }
      .nav a.ativo {
        background: var(--cor-sidebar-ativo);
        color: #fff;
        border-radius: 0 8px 8px 0;
        margin-right: 12px;
      }
      .admin-area {
        margin-top: auto;
        padding: 12px 24px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
      .admin-btn {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 100%;
        background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%);
        color: #fff;
        border: none;
        border-radius: 10px;
        padding: 12px 12px;
        font-weight: 700;
        font-size: 13.5px;
        cursor: pointer;
        box-shadow: 0 8px 18px rgba(37, 99, 235, 0.25);
        transition: transform 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease;
      }
      .admin-btn:hover {
        transform: translateY(-1px);
        box-shadow: 0 10px 22px rgba(37, 99, 235, 0.32);
      }
      .admin-btn-ativo {
        outline: 1px solid rgba(255,255,255,0.45);
        opacity: 0.95;
      }
      .rodape {
        padding: 16px 24px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
      .tema-area {
        padding: 12px 24px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
      .tema-btn {
        display: flex;
        align-items: center;
        gap: 10px;
        width: 100%;
        padding: 10px 12px;
        border: 1px solid rgba(255, 255, 255, 0.14);
        border-radius: 8px;
        background: rgba(255, 255, 255, 0.04);
        color: #e2e8f0;
        font-size: 13px;
        font-weight: 600;
        text-align: left;
      }
      .tema-btn:hover { background: rgba(255, 255, 255, 0.1); }
      .tema-icone { width: 18px; text-align: center; font-size: 17px; }
      .usuario-nome { font-size: 13.5px; font-weight: 600; color: #fff; }
      .usuario-papel { font-size: 12px; color: #94a3b8; margin-bottom: 10px; }
      .sair {
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: #e2e8f0;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 13px;
        width: 100%;
      }
      .sair:hover { background: rgba(255, 255, 255, 0.08); }
      .conteudo {
        flex: 1;
        padding: 32px 40px;
        overflow-x: auto;
      }
    `,
  ],
})
export class ShellComponent implements OnInit {
  auth = inject(AuthService);
  // O serviço centraliza a preferência para que a sidebar seja a única responsável pelo controle visual.
  tema = inject(ThemeService);

  isAdmin(): boolean {
    return this.auth.usuario()?.papel === 'ADMIN';
  }

  ngOnInit(): void {
    // Recarrega o perfil ao atualizar a página (GET /auth/me), pois o signal `usuario` é volátil.
    if (!this.auth.usuario()) {
      this.auth.carregarPerfil().subscribe();
    }
  }
}
