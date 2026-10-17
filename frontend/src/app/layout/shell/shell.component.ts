import { Component, OnInit, inject, signal } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';
import { ThemeService } from '../../core/services/theme.service';
import { ProcessManagerService } from '../../core/services/process-manager.service';

@Component({
  selector: 'app-shell',
  standalone: true,
  imports: [RouterOutlet, RouterLink, RouterLinkActive, DecimalPipe],
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
          @if (canWrite()) {
          <a routerLink="/benchmark" routerLinkActive="ativo">
            <svg class="nav-icone" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M4 19V5" /><path d="M4 19h16" /><rect x="7" y="13" width="3" height="4" rx=".5" /><rect x="12" y="9" width="3" height="8" rx=".5" /><rect x="17" y="5" width="3" height="12" rx=".5" />
            </svg>
            Benchmark
          </a>
          }
          <a routerLink="/historico" routerLinkActive="ativo">
            <svg class="nav-icone" viewBox="0 0 24 24" aria-hidden="true">
              <circle cx="12" cy="12" r="8" /><path d="M12 8v4l3 2" /><path d="M4 12H2" />
            </svg>
            Histórico
          </a>
        </nav>

        <section class="process-area" aria-label="Gerenciador de processos">
          <button
            class="process-launch"
            type="button"
            [class.em-andamento]="haProcessosEmAndamento()"
            [attr.aria-expanded]="painelProcessosAberto()"
            aria-controls="process-panel"
            (click)="painelProcessosAberto.update((open) => !open)"
          >
            <span class="process-launch-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24">
                <path d="M4 17v-2a3 3 0 0 1 3-3h10a3 3 0 0 0 3-3V7" />
                <circle cx="20" cy="5" r="2" />
                <circle cx="4" cy="19" r="2" />
                <path d="M12 12v7" />
                <circle cx="12" cy="21" r="1" />
              </svg>
            </span>
            <span class="process-launch-copy">
              <strong>Processos</strong>
              <small>
                {{ resumoProcessos() }}
              </small>
            </span>
            @if (haProcessosEmAndamento()) {
              <span class="process-dot" aria-label="Em andamento"></span>
            }
          </button>

          @if (painelProcessosAberto()) {
            <section class="process-panel" id="process-panel" aria-label="Processos em execução">
            <header class="process-panel-header">
                <div>
                  <p>GERENCIADOR</p>
                  <h2>Processos</h2>
                </div>
                <button type="button" class="process-close" aria-label="Fechar processos" (click)="painelProcessosAberto.set(false)">×</button>
              </header>
              <div class="process-panel-wrapper">
                @for (tarefa of processos.tasks(); track tarefa.id) {
                <div class="process-item">
                  <div class="process-item-title">
                    <span class="process-item-icon" aria-hidden="true">
                      {{ tarefa.kind === 'analysis' ? 'IA' : 'BM' }}
                    </span>
                    <div>
                      <strong>{{ tarefa.title }}</strong>
                      <small>{{ tarefa.description }}</small>
                    </div>
                  </div>
                  @if (tarefa.status === 'running' && canWrite()) {
                    <p class="process-status">{{ tarefa.progress === null ? 'Em andamento' : tarefa.progress + '% concluído' }}</p>
                    <div class="process-track" [class.indeterminado]="tarefa.progress === null" role="progressbar" [attr.aria-valuenow]="tarefa.progress" aria-valuemin="0" aria-valuemax="100" [attr.aria-label]="'Progresso: ' + (tarefa.progress === null ? 'indeterminado' : tarefa.progress + '%')">
                      <div class="process-fill" [class.indeterminado]="tarefa.progress === null" [style.width.%]="tarefa.progress"></div>
                    </div>
                  } @else if (tarefa.status === 'completed') {
                    <p class="process-done">Concluído</p>
                  } @else if (tarefa.status === 'failed') {
                    <p class="process-error">{{ tarefa.error || 'A operação falhou.' }}</p>
                  } @else {
                    <p class="process-status">{{ tarefa.description }}</p>
                  }
                  @if (tarefa.status === 'running' && tarefa.error) {
                    <p class="process-error">{{ tarefa.error }}</p>
                  }
                  <div class="process-meta">
                    <span>{{ formatarDuracao(tarefa.elapsedSeconds) }}</span>
                    @if (tarefa.status === 'running') {
                      <button
                        type="button"
                        class="process-dismiss process-cancel"
                        [disabled]="tarefa.cancelling"
                        (click)="processos.cancelTask(tarefa.id)"
                      >
                        {{ tarefa.cancelling ? 'Cancelando…' : 'Cancelar' }}
                      </button>
                    } @else if (tarefa.kind === 'analysis' && tarefa.executionId) {
                      <a class="process-dismiss" [routerLink]="['/analises', tarefa.executionId, tarefa.status === 'completed' ? 'resultados' : 'execucao']">
                        {{ tarefa.status === 'completed' ? 'Ver resultados' : 'Abrir' }}
                      </a>
                    } @else {
                      <button type="button" class="process-dismiss" (click)="processos.dismissTask(tarefa.id)">Dispensar</button>
                    }
                  </div>
                </div>
              }
            </div>
              @if (processos.datasetImport(); as processo) {
                <div class="process-item">
                  <div class="process-item-title">
                    <span class="process-item-icon" aria-hidden="true">CSV</span>
                    <div>
                      <strong>Importação de dataset</strong>
                      <small>{{ processo.filename }}</small>
                    </div>
                  </div>
                  @if (processo.status === 'uploading') {
                    <p class="process-status">Enviando arquivo · {{ processo.progress === null ? 'Preparando…' : processo.progress + '%' }}</p>
                    <div class="process-track" role="progressbar" [attr.aria-valuenow]="processo.progress" aria-valuemin="0" aria-valuemax="100" aria-label="Progresso do upload">
                      <div class="process-fill" [class.indeterminado]="processo.progress === null" [style.width.%]="processo.progress"></div>
                    </div>
                  } @else if (processo.status === 'processing') {
                    <p class="process-status">Arquivo enviado. Validando e gravando transações…</p>
                    <div class="process-track indeterminado"><div class="process-fill"></div></div>
                  } @else if (processo.status === 'starting') {
                    <p class="process-status">Registrando importação no servidor…</p>
                    <div class="process-track indeterminado"><div class="process-fill"></div></div>
                  } @else if (processo.status === 'cancelling') {
                    <p class="process-status">{{ processo.error || 'Cancelando no servidor e revertendo os dados parciais…' }}</p>
                    <div class="process-track indeterminado"><div class="process-fill"></div></div>
                  } @else if (processo.status === 'completed') {
                    <p class="process-done">Importação concluída · {{ processo.dataset?.total_registros | number: '1.0-0' : 'pt-BR' }} registros</p>
                  } @else if (processo.status === 'cancelled') {
                    <p class="process-status">{{ processo.error }}</p>
                  } @else {
                    <p class="process-error">{{ processo.error }}</p>
                  }
                  <div class="process-meta">
                    <span>{{ formatarTamanho(processo.bytesSent) }} / {{ formatarTamanho(processo.size) }}</span>
                    <span>{{ formatarDuracao(processo.elapsedSeconds) }}</span>
                  </div>
                  @if (canWrite() && (processo.status === 'starting' || processo.status === 'uploading' || processo.status === 'processing')) {
                    <button type="button" class="process-dismiss process-cancel" (click)="processos.cancelDatasetImport()">Cancelar</button>
                  } @else if (processo.status === 'completed' || processo.status === 'failed' || processo.status === 'cancelled') {
                    <button type="button" class="process-dismiss" (click)="processos.dismissDatasetImport()">Dispensar</button>
                  }
                </div>
              } @if (!processos.datasetImport() && processos.tasks().length === 0) {
                <div class="process-empty">
                  <span aria-hidden="true">✓</span>
                  <p>Nenhum processo ativo no momento.</p>
                  <small>Operações continuam acompanhadas enquanto você navega pelo sistema.</small>
                </div>
              }
            </section>
          }
        </section>

        @if (isAdmin()) {
          <div class="admin-area">
            <button class="admin-btn" type="button" routerLink="/admin/usuarios/novo" routerLinkActive="admin-btn-ativo">
              + Criar usuário
            </button>
          </div>
        }

        <div class="rodape">
          @if (auth.usuario(); as u) {
            <div class="usuario-cabecalho">
              <p class="usuario-nome">{{ u.nome }}</p>
              <button
                class="tema-btn"
                type="button"
                (click)="tema.alternar()"
                [attr.aria-pressed]="tema.escuro()"
                [attr.aria-label]="tema.escuro() ? 'Ativar tema claro' : 'Ativar tema escuro'"
                [title]="tema.escuro() ? 'Ativar tema claro' : 'Ativar tema escuro'"
              >
                <span aria-hidden="true">{{ tema.escuro() ? '☀' : '☾' }}</span>
              </button>
            </div>
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
      .process-area { position: relative; margin: auto 12px 16px; }
      .process-launch { display: flex; align-items: center; gap: 10px; width: 100%; padding: 11px; border: 1px solid rgba(148, 163, 184, .32); border-radius: 10px; background: rgba(148, 163, 184, .08); color: #e2e8f0; text-align: left; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
      .process-launch:hover, .process-launch.em-andamento { border-color: rgba(96, 165, 250, .7); background: rgba(37, 99, 235, .16); }
      .process-launch-icon { display: grid; place-items: center; flex: 0 0 34px; width: 34px; height: 34px; border: 1px solid rgba(96, 165, 250, .42); border-radius: 9px; color: #93c5fd; }
      .process-launch-icon svg { width: 19px; height: 19px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
      .process-launch-copy { display: grid; gap: 3px; min-width: 0; flex: 1; }
      .process-launch-copy strong { font-size: 13px; }
      .process-launch-copy small { overflow: hidden; color: #94a3b8; font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
      .process-dot { flex: 0 0 8px; width: 8px; height: 8px; border-radius: 50%; background: #60a5fa; box-shadow: 0 0 0 4px rgba(96, 165, 250, .15); animation: process-pulse 1.6s ease-in-out infinite; }
      .process-panel { position: absolute; z-index: 30; bottom: calc(100% + 9px); left: 0; width: 100%; min-width: 240px; max-height: 65vh; overflow-y: auto; padding: 15px; border: 1px solid var(--cor-borda); border-radius: 11px; background: var(--cor-superficie); color: var(--cor-texto); box-shadow: 0 16px 40px rgba(0, 0, 0, .32); }
      .process-panel-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 10px; margin-bottom: 14px; }
      .process-panel-header p { margin: 0 0 3px; color: var(--cor-primaria); font-size: 9px; font-weight: 700; letter-spacing: .12em; }
      .process-panel-header h2 { margin: 0; font-size: 16px; }
      .process-close { width: 28px; height: 28px; border: 1px solid var(--cor-borda); border-radius: 7px; background: var(--cor-superficie-suave); color: var(--cor-texto-suave); font-size: 18px; line-height: 1; cursor: pointer; }
      .process-panel-wrapper { display: grid; gap: 10px; }
      .process-item { display: grid; gap: 10px; padding: 11px; border: 1px solid var(--cor-borda); border-radius: 9px; background: var(--cor-superficie-suave); }
      .process-item-title { display: flex; align-items: center; gap: 9px; min-width: 0; }
      .process-item-title > div { display: grid; gap: 3px; min-width: 0; }
      .process-item-title strong { font-size: 11px; }
      .process-item-title small { overflow: hidden; color: var(--cor-texto-suave); font-size: 10px; text-overflow: ellipsis; white-space: nowrap; }
      .process-item-icon { display: grid; place-items: center; flex: 0 0 30px; width: 30px; height: 30px; border-radius: 8px; background: color-mix(in srgb, var(--cor-primaria) 14%, var(--cor-superficie)); color: var(--cor-primaria); font-size: 9px; font-weight: 800; }
      .process-status, .process-done, .process-error { margin: 0; font-size: 10px; line-height: 1.45; }
      .process-status { color: var(--cor-texto-suave); }
      .process-done { color: var(--cor-sucesso-texto); }
      .process-error { color: var(--cor-erro-texto); }
      .process-track { height: 6px; overflow: hidden; border-radius: 999px; background: var(--cor-borda); }
      .process-fill { height: 100%; border-radius: inherit; background: var(--cor-primaria); transition: width .25s ease; }
      .process-track.indeterminado .process-fill, .process-fill.indeterminado { width: 38%; animation: process-move 1.4s ease-in-out infinite alternate; }
      .process-meta { display: flex; justify-content: space-between; gap: 6px; color: var(--cor-texto-suave); font-size: 9px; }
      .process-dismiss { justify-self: end; padding: 5px 8px; border: 1px solid var(--cor-borda); border-radius: 6px; background: transparent; color: var(--cor-texto-suave); font-size: 10px; cursor: pointer; }
      a.process-dismiss { text-decoration: none; }
      .process-cancel { border-color: var(--cor-erro-texto); color: var(--cor-erro-texto); }
      .process-cancel:hover:not(:disabled) { background: var(--cor-erro-bg); }
      .process-cancel:disabled { cursor: wait; opacity: .6; }
      .process-empty { display: grid; justify-items: center; gap: 7px; padding: 16px 8px 10px; text-align: center; }
      .process-empty span { display: grid; place-items: center; width: 28px; height: 28px; border-radius: 50%; background: var(--cor-sucesso-bg); color: var(--cor-sucesso-texto); font-size: 13px; }
      .process-empty p { margin: 0; font-size: 11px; font-weight: 600; }
      .process-empty small { color: var(--cor-texto-suave); font-size: 10px; line-height: 1.45; }
      @keyframes process-pulse { 50% { opacity: .45; } }
      @keyframes process-move { from { transform: translateX(-20%); } to { transform: translateX(190%); } }
      .admin-area {
        margin-top: 0;
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
        padding: 16px 18px 0;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
      }
      .usuario-cabecalho { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 3px; }
      .usuario-nome { min-width: 0; overflow: hidden; font-size: 13.5px; font-weight: 600; color: #fff; text-overflow: ellipsis; white-space: nowrap; }
      .tema-btn { display: grid; place-items: center; flex: 0 0 36px; width: 36px; height: 36px; border: 1px solid rgba(255, 255, 255, .38); border-radius: 9px; background: rgba(255, 255, 255, .09); color: #f8fafc; font-size: 19px; cursor: pointer; transition: background .15s ease, border-color .15s ease; }
      .tema-btn:hover { border-color: rgba(147, 197, 253, .85); background: rgba(147, 197, 253, .2); }
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
  processos = inject(ProcessManagerService);
  painelProcessosAberto = signal(false);

  importacaoEmAndamento(): boolean {
    const status = this.processos.datasetImport()?.status;
    return (
      status === 'starting' ||
      status === 'uploading' ||
      status === 'processing' ||
      status === 'cancelling'
    );
  }

  haProcessosEmAndamento(): boolean {
    return (
      this.importacaoEmAndamento() ||
      this.processos.tasks().some((task) => task.status === 'running')
    );
  }

  resumoProcessos(): string {
    const ativos = this.processos.tasks().filter((task) => task.status === 'running').length;
    if (this.importacaoEmAndamento()) return 'Importação em andamento';
    if (ativos) return `${ativos} operação(ões) em andamento`;
    const importStatus = this.processos.datasetImport()?.status;
    if (importStatus === 'completed') return 'Importação concluída';
    if (importStatus === 'failed') return 'Importação com erro';
    return 'Nenhuma tarefa ativa';
  }

  formatarTamanho(bytes: number): string {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  formatarDuracao(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return minutes ? `${minutes} min ${remaining} s` : `${remaining} s`;
  }

  isAdmin(): boolean {
    return this.auth.usuario()?.papel === 'ADMIN';
  }

  canWrite(): boolean {
    const papel = this.auth.usuario()?.papel;
    return papel === 'ADMIN' || papel === 'ANALISTA';
  }

  ngOnInit(): void {
    // Recarrega o perfil ao atualizar a página (GET /auth/me), pois o signal `usuario` é volátil.
    if (!this.auth.usuario()) {
      this.auth.carregarPerfil().subscribe();
    }
  }
}
