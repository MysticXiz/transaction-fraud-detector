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
          <a routerLink="/dashboard" routerLinkActive="ativo">
            <svg class="nav-icone" viewBox="0 0 24 24" aria-hidden="true">
              <rect x="4" y="4" width="6" height="6" rx="1" /><rect x="14" y="4" width="6" height="6" rx="1" />
              <rect x="4" y="14" width="6" height="6" rx="1" /><rect x="14" y="14" width="6" height="6" rx="1" />
            </svg>
            Dashboard
          </a>
          <a routerLink="/datasets" routerLinkActive="ativo">
            <svg class="nav-icone" viewBox="0 0 24 24" aria-hidden="true">
              <ellipse cx="12" cy="5" rx="7" ry="3" /><path d="M5 5v7c0 1.7 3.1 3 7 3s7-1.3 7-3V5" /><path d="M5 12v7c0 1.7 3.1 3 7 3s7-1.3 7-3v-7" />
            </svg>
            Datasets
          </a>
          <a routerLink="/benchmark" routerLinkActive="ativo">
            <svg class="nav-icone" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 19V5" /><path d="M4 19h16" /><rect x="7" y="13" width="3" height="4" rx=".5" /><rect x="12" y="9" width="3" height="8" rx=".5" /><rect x="17" y="5" width="3" height="12" rx=".5" />
            </svg>
            Benchmark
          </a>
          <a routerLink="/historico" routerLinkActive="ativo">
            <svg class="nav-icone" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /><path d="M4 12H2" />
            </svg>
            Histórico
          </a>
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
          <div class="acoes-conta">
            <a class="conta-link" routerLink="/minha-conta" routerLinkActive="conta-link-ativo">Minha conta</a>
            <button class="sair" type="button" (click)="auth.logout()" aria-label="Sair da conta" title="Sair">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M10 4H6a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h4" />
                <path d="M14 16l4-4-4-4" /><path d="M18 12H9" />
              </svg>
            </button>
          </div>
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
        display: flex;
        align-items: center;
        gap: 11px;
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
      .nav-icone {
        width: 18px;
        height: 18px;
        flex: 0 0 18px;
        fill: none;
        stroke: currentColor;
        stroke-linecap: round;
        stroke-linejoin: round;
        stroke-width: 1.8;
      }
      .admin-area {
        margin-top: auto;
        padding: 18px 24px;
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
        padding: 18px 24px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
      .tema-area {
        padding: 18px 24px;
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
      .acoes-conta { display: flex; align-items: stretch; gap: 8px; }
      .conta-link {
        display: flex;
        align-items: center;
        justify-content: center;
        flex: 1;
        color: #93c5fd;
        font-size: 13px;
        font-weight: 600;
        border: 1px solid rgba(147, 197, 253, 0.35);
        border-radius: 6px;
        padding: 6px 8px;
      }
      .conta-link:hover, .conta-link-ativo { color: #fff; background: rgba(147, 197, 253, 0.1); }
      .sair {
        flex: 0 0 38px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: rgba(220, 38, 38, 0.16);
        border: 1px solid rgba(248, 113, 113, 0.55);
        color: #fca5a5;
        border-radius: 6px;
        padding: 6px;
        line-height: 1;
      }
      .sair svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-linecap: round; stroke-linejoin: round; stroke-width: 1.8; }
      .sair:hover { background: #dc2626; border-color: #ef4444; color: #fff; }
      .conteudo {
        flex: 1;
        padding: 40px 40px 32px;
        overflow-x: auto;
      }
      @media (max-width: 900px) {
        .conteudo { padding: 36px 28px 28px; }
      }
      @media (max-width: 640px) {
        .conteudo { padding: 28px 16px 24px; }
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
