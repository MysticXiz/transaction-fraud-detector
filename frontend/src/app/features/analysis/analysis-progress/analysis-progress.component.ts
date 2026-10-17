import { DecimalPipe } from '@angular/common';
import { Component, DestroyRef, OnInit, effect, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { interval } from 'rxjs';
import { AnalysisService } from '../../../core/services/analysis.service';
import { ExecucaoAnalise } from '../../../core/models/analise.model';
import { StatusExecucao } from '../../../core/models/enums';
import { ManagedProcess, ProcessManagerService } from '../../../core/services/process-manager.service';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-analysis-progress',
  standalone: true,
  imports: [DecimalPipe],
  template: `
    <section class="progress-page" aria-labelledby="progress-title">
      <header class="page-header">
        <div class="page-header__copy">
          <p class="page-eyebrow">Análise em andamento</p>
          <h1 id="progress-title" class="page-title">Acompanhamento</h1>
        </div>
      </header>

      <div class="df-card progress-card">
        <div class="status-heading">
          <div>
            <h2>{{ tituloEstado() }}</h2>
            <p class="status-description">{{ descricaoEstado() }}</p>
          </div>
          @if (polling()) {
            <span class="live-indicator"><span></span> Atualizando</span>
          }
        </div>

        <div
          class="progress-track"
          role="progressbar"
          [attr.aria-valuenow]="progresso()"
          aria-valuemin="0"
          aria-valuemax="100"
          [attr.aria-label]="'Progresso da análise: ' + progresso() + '%'"
        >
          <div class="progress-fill" [style.width.%]="progresso()"></div>
        </div>

        <div class="progress-summary">
          <strong>{{ progresso() }}%</strong>
          <span>{{ analisadas() | number }} de {{ totalRegistros() | number }} transações</span>
        </div>

        <div class="metrics-grid">
          <div class="metric">
            <span class="metric-label">Suspeitas encontradas</span>
            <strong>{{ suspeitas() | number }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">Tempo decorrido</span>
            <strong>{{ formatarDuracao(tempoDecorrido()) }}</strong>
          </div>
          <div class="metric">
            <span class="metric-label">Conclusão estimada</span>
            <strong>{{ estimativaConclusao() }}</strong>
          </div>
        </div>

        @if (erro()) {
          <div class="df-alerta df-alerta-erro" role="alert">
            <span>{{ erro() }}</span>
          </div>
        }
        @if (mensagemEstado()) {
          <div
            class="state-message"
            [class.state-error]="status() === Status.FALHA"
            [class.state-cancelled]="status() === Status.CANCELADA"
            role="status"
          >
            {{ mensagemEstado() }}
          </div>
        }

        <footer class="actions">
          @if (ativa() && !erro() && !cancelando() && canWrite()) {
            <button class="df-btn df-btn-secundario" type="button" (click)="cancelar()">
              Cancelar análise
            </button>
          }
          @if (cancelando()) {
            <span class="action-hint">Solicitando cancelamento…</span>
          }
          @if (erro() && ativa()) {
            <button class="df-btn df-btn-primary" type="button" (click)="retomarAcompanhamento()">
              Tentar novamente
            </button>
          }
          @if (!ativa() || erro()) {
            <button class="df-btn df-btn-primary" type="button" (click)="voltar()">
              {{ status() === Status.CONCLUIDA ? 'Ver resultados' : 'Voltar para análises' }}
            </button>
          }
        </footer>
      </div>
    </section>
  `,
  styles: [
    `
      :host { display: block; }
      .progress-page { width: min(100%, 760px); margin: 0 auto; }
      .progress-card { display: grid; gap: 22px; }
      .status-heading { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; }
      .status-heading h2 { font-size: 18px; font-weight: 700; }
      .status-description { margin-top: 6px; color: var(--cor-texto-suave); font-size: 13px; }
      .live-indicator { display: inline-flex; align-items: center; gap: 7px; color: var(--cor-sucesso-texto); font-size: 12px; white-space: nowrap; }
      .live-indicator span { width: 8px; height: 8px; border-radius: 50%; background: currentColor; box-shadow: 0 0 0 3px color-mix(in srgb, currentColor 18%, transparent); }
      .progress-track { height: 12px; overflow: hidden; border: 1px solid var(--cor-borda); border-radius: 999px; background: var(--cor-superficie-suave); }
      .progress-fill { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--cor-primaria), #60a5fa); transition: width .45s ease; }
      .progress-summary { display: flex; align-items: baseline; justify-content: space-between; gap: 12px; margin-top: -14px; }
      .progress-summary strong { color: var(--cor-primaria); font-size: 24px; }
      .progress-summary span { color: var(--cor-texto-suave); font-size: 13px; text-align: right; }
      .metrics-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
      .metric { display: grid; gap: 8px; min-width: 0; padding: 14px; border: 1px solid var(--cor-borda); border-radius: 8px; background: var(--cor-superficie-suave); }
      .metric-label { color: var(--cor-texto-suave); font-size: 12px; }
      .metric strong { color: var(--cor-texto); font-size: 16px; }
      .state-message { padding: 12px 14px; border: 1px solid var(--cor-borda); border-radius: 8px; background: var(--cor-superficie-suave); color: var(--cor-texto); font-size: 13px; }
      .state-error { border-color: var(--cor-erro-texto); background: var(--cor-erro-bg); color: var(--cor-erro-texto); }
      .state-cancelled { border-color: var(--cor-aviso-texto); background: var(--cor-aviso-bg); color: var(--cor-aviso-texto); }
      .actions { display: flex; align-items: center; justify-content: flex-end; gap: 10px; padding-top: 4px; }
      .action-hint { color: var(--cor-texto-suave); font-size: 13px; }
      @media (max-width: 560px) {
        .progress-card { gap: 18px; }
        .metrics-grid { grid-template-columns: 1fr; }
        .metric { grid-template-columns: 1fr auto; align-items: center; }
        .progress-summary { align-items: flex-start; flex-direction: column; gap: 0; }
      }
    `,
  ],
})
export class AnalysisProgressComponent implements OnInit {
  private auth = inject(AuthService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private analysisService = inject(AnalysisService);
  private processes = inject(ProcessManagerService);
  private destroyRef = inject(DestroyRef);
  private executionStartedAt: number | null = null;
  private navigatedExecutionId: number | null = null;

  readonly Status = StatusExecucao;

  canWrite(): boolean {
    const role = this.auth.usuario()?.papel;
    return role === 'ADMIN' || role === 'ANALISTA';
  }
  private executionId = signal<number | null>(null);
  progresso = signal(0);
  erro = signal<string | null>(null);
  status = signal<StatusExecucao>(StatusExecucao.PENDENTE);
  ativa = signal(true);
  polling = signal(false);
  cancelando = signal(false);
  analisadas = signal(0);
  totalRegistros = signal(0);
  suspeitas = signal(0);
  tempoDecorrido = signal(0);
  mensagemEstado = signal<string | null>(null);

  constructor() {
    effect(() => {
      const id = this.executionId();
      if (id === null) return;
      const process = this.processes.getAnalysisProcess(id);
      if (process) this.aplicarProcesso(process);
    });
    interval(1000)
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(() => this.atualizarTempoDecorrido());
  }

  ngOnInit(): void {
    const idExecucao = Number(this.route.snapshot.paramMap.get('id'));
    if (!Number.isSafeInteger(idExecucao) || idExecucao < 1) {
      this.ativa.set(false);
      this.erro.set('O identificador da análise é inválido.');
      return;
    }
    this.executionId.set(idExecucao);
    this.processes.startAnalysisTracking(idExecucao);
  }

  tituloEstado(): string {
    switch (this.status()) {
      case StatusExecucao.CONCLUIDA:
        return 'Análise concluída';
      case StatusExecucao.FALHA:
        return 'Falha ao processar a análise';
      case StatusExecucao.CANCELADA:
        return 'Análise cancelada';
      case StatusExecucao.PENDENTE:
        return 'Análise na fila';
      default:
        return 'Processando análise';
    }
  }

  descricaoEstado(): string {
    if (this.status() === StatusExecucao.PENDENTE) {
      return 'A análise foi registrada e começará assim que o processamento estiver disponível.';
    }
    if (this.status() === StatusExecucao.EM_ANDAMENTO) {
      return 'Os resultados são salvos em blocos e o progresso é atualizado periodicamente.';
    }
    return 'Resumo atualizado a partir do estado persistido da execução.';
  }

  estimativaConclusao(): string {
    const percent = this.progresso();
    const elapsed = this.tempoDecorrido();
    if (!this.ativa() || percent >= 100) return 'Concluída';
    if (percent <= 0 || elapsed <= 0) return 'Calculando…';
    return `~${this.formatarDuracao(Math.ceil((elapsed * (100 - percent)) / percent))}`;
  }

  formatarDuracao(seconds: number): string {
    const safeSeconds = Math.max(0, Math.floor(seconds));
    const hours = Math.floor(safeSeconds / 3600);
    const minutes = Math.floor((safeSeconds % 3600) / 60);
    const remaining = safeSeconds % 60;
    if (hours > 0) return `${hours}h ${minutes}min`;
    if (minutes > 0) return `${minutes}min ${remaining}s`;
    return `${remaining}s`;
  }

  cancelar(): void {
    const idExecucao = Number(this.route.snapshot.paramMap.get('id'));
    if (!this.ativa() || this.cancelando()) return;
    this.cancelando.set(true);
    this.erro.set(null);
    this.analysisService.cancelar(idExecucao).pipe(
      takeUntilDestroyed(this.destroyRef)
    ).subscribe({
      next: () => {
        this.processes.markAnalysisCancelled(idExecucao);
        this.status.set(StatusExecucao.CANCELADA);
        this.ativa.set(false);
        this.cancelando.set(false);
        this.mensagemEstado.set('O cancelamento foi solicitado. Nenhum novo bloco será iniciado.');
      },
      error: (error: { error?: { detail?: unknown } }) => {
        this.cancelando.set(false);
        this.erro.set(
          typeof error.error?.detail === 'string'
            ? error.error.detail
            : 'Não foi possível cancelar a análise. Atualize o status ou tente novamente.'
        );
      },
    });
  }

  retomarAcompanhamento(): void {
    const idExecucao = Number(this.route.snapshot.paramMap.get('id'));
    this.erro.set(null);
    this.mensagemEstado.set(null);
    this.polling.set(true);
    this.processes.startAnalysisTracking(idExecucao);
  }

  voltar(): void {
    if (this.status() === StatusExecucao.CONCLUIDA) {
      const idExecucao = Number(this.route.snapshot.paramMap.get('id'));
      this.router.navigate(['/analises', idExecucao, 'resultados']);
      return;
    }
    this.router.navigateByUrl('/analises');
  }

  private aplicarProcesso(process: ManagedProcess): void {
    const execution = process.execution;
    this.polling.set(process.status === 'running');
    this.erro.set(process.status === 'failed' && execution?.status !== StatusExecucao.FALHA
      ? process.error
      : null);
    if (!execution) return;
    this.status.set(execution.status);
    this.progresso.set(Math.max(0, Math.min(execution.progresso_percentual ?? 0, 100)));
    this.analisadas.set(execution.total_analisadas);
    this.totalRegistros.set(execution.total_registros ?? 0);
    this.suspeitas.set(execution.total_suspeitas);
    this.executionStartedAt = process.startedAt;
    if (this.executionStartedAt !== null) {
      this.atualizarTempoDecorrido();
    }

    if (process.status === 'completed') {
      this.ativa.set(false);
      this.mensagemEstado.set('Todos os resultados foram persistidos com sucesso.');
      this.progresso.set(100);
      if (this.navigatedExecutionId !== execution.id_execucao) {
        this.navigatedExecutionId = execution.id_execucao;
        this.router.navigate(['/analises', execution.id_execucao, 'resultados']);
      }
    } else if (process.status === 'failed' && execution.status === StatusExecucao.FALHA) {
      this.ativa.set(false);
      this.mensagemEstado.set(
        execution.mensagem_erro ?? 'A execução falhou. Consulte os detalhes ou retorne.'
      );
    } else if (process.status === 'cancelled') {
      this.ativa.set(false);
      this.mensagemEstado.set('A análise foi cancelada. Os blocos já concluídos permanecem registrados.');
    } else {
      this.ativa.set(true);
      this.mensagemEstado.set(null);
    }
  }

  private atualizarTempoDecorrido(): void {
    if (this.executionStartedAt === null || !this.ativa()) return;
    this.tempoDecorrido.set(Math.max(0, Math.floor((Date.now() - this.executionStartedAt) / 1000)));
  }
}
