import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { HttpErrorResponse } from '@angular/common/http';
import { AnalysisService } from '../../core/services/analysis.service';
import { AuthService } from '../../core/services/auth.service';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ExecucaoAnalise } from '../../core/models/analise.model';
import { ModoExecucao, StatusExecucao } from '../../core/models/enums';
import { StyledSelectComponent, StyledSelectOption } from '../../shared/components/styled-select/styled-select.component';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, DecimalPipe, ReactiveFormsModule, StatusBadgeComponent, StyledSelectComponent],
  template: `
    <div class="df-pagina">
      <header class="page-header">
        <div class="page-header__copy">
          <p class="page-eyebrow">Acompanhamento</p>
          <h1 class="page-title">Histórico de Execuções</h1>
          <p class="page-subtitle">Todas as análises executadas, com filtros por status e modo.</p>
        </div>
      </header>

      @if (erro()) {
        <div class="df-alerta df-alerta-erro" role="alert">
          <span>{{ erro() }}</span>
          <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="erro.set(null)">×</button>
        </div>
      }
      @if (sucesso()) {
        <div class="df-alerta df-alerta-sucesso" role="status">
          <span>{{ sucesso() }}</span>
          <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="sucesso.set(null)">×</button>
        </div>
      }

      <div class="df-card sem-padding">
        <form [formGroup]="filtroForm" class="barra-filtros">
          <app-styled-select class="filtro-select" formControlName="status" ariaLabel="Filtrar por status" [opcoes]="opcoesStatus" />
          <app-styled-select class="filtro-select" formControlName="modo" ariaLabel="Filtrar por modo" [opcoes]="opcoesModo" />
        </form>

        @if (carregando()) {
          <div class="carregando-lista" role="status" aria-live="polite">
            <span class="df-spinner df-spinner-suave" aria-hidden="true"></span>
            <p>Carregando execuções…</p>
          </div>
        } @else if (execucoes().length) {
          <div class="tabela-wrap">
            <table class="df-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Dataset</th>
                  <th>Modo</th>
                  <th>Status</th>
                  <th>Tempo</th>
                  <th style="text-align:right">Ações</th>
                </tr>
              </thead>
              <tbody>
                @for (e of execucoes(); track e.id_execucao) {
                  <tr>
                    <td>#{{ e.id_execucao }}</td>
                    <td>{{ e.dataset_nome ?? '—' }}</td>
                    <td>{{ e.modo_execucao === 'SEQUENCIAL' ? 'Sequencial' : 'Paralelo (' + e.num_workers + 'w)' }}</td>
                    <td><app-status-badge [status]="e.status" /></td>
                    <td>{{ e.tempo_total_s ? (e.tempo_total_s | number: '1.2-2' : 'pt-BR') + 's' : '—' }}</td>
                    <td style="text-align:right">
                      <div class="acoes-execucao">
                        <a class="df-link" [routerLink]="['/analises', e.id_execucao, 'resultados']">Ver resultados</a>
                        @if (canWrite()) {
                        <button
                          type="button"
                          class="botao-excluir"
                          [disabled]="e.status === Status.PENDENTE || e.status === Status.EM_ANDAMENTO || excluindoId() === e.id_execucao"
                          [attr.aria-label]="'Excluir execução ' + e.id_execucao"
                          [title]="e.status === Status.PENDENTE || e.status === Status.EM_ANDAMENTO ? 'Não é possível excluir uma execução em andamento' : 'Excluir execução'"
                          (click)="excluir(e)"
                        >
                          {{ excluindoId() === e.id_execucao ? 'Excluindo…' : 'Excluir' }}
                        </button>
                        }
                      </div>
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        } @else {
          <div class="df-estado sem-borda">
            <span class="df-estado-icone" aria-hidden="true">▤</span>
            <h2>Nenhuma execução encontrada</h2>
            <p>Ajuste os filtros de status ou modo para ver outras execuções.</p>
          </div>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .sem-padding { padding: 0; overflow: visible; }
      .barra-filtros { position: relative; z-index: 2; display: flex; gap: 12px; padding: 18px 24px; border-bottom: 1px solid var(--cor-borda); }
      .filtro-select { width: 180px; }
      .tabela-wrap { overflow-x: auto; }
      .carregando-lista { display: flex; align-items: center; gap: 10px; padding: 32px 24px; color: var(--cor-texto-suave); font-size: 13px; }
      .sem-borda { border: 0; border-radius: 0; padding: 48px 20px; }
      .acoes-execucao { display: inline-flex; align-items: center; justify-content: flex-end; gap: 14px; }
      .botao-excluir { padding: 4px 8px; border: 1px solid var(--cor-erro-texto); border-radius: 5px; background: transparent; color: var(--cor-erro-texto); font: inherit; font-size: 12px; cursor: pointer; }
      .botao-excluir:hover:not(:disabled) { background: var(--cor-erro-bg); }
      .botao-excluir:disabled { opacity: .5; cursor: not-allowed; }
    `,
  ],
})
export class HistoryComponent implements OnInit {
  private auth = inject(AuthService);
  private analysisService = inject(AnalysisService);

  canWrite(): boolean {
    const role = this.auth.usuario()?.papel;
    return role === 'ADMIN' || role === 'ANALISTA';
  }
  private fb = inject(FormBuilder);

  Status = StatusExecucao;
  Modo = ModoExecucao;
  execucoes = signal<ExecucaoAnalise[]>([]);
  carregando = signal(true);
  erro = signal<string | null>(null);
  sucesso = signal<string | null>(null);
  excluindoId = signal<number | null>(null);

  opcoesStatus: StyledSelectOption[] = [
    { valor: 'TODOS', rotulo: 'Todos os Status' },
    { valor: StatusExecucao.CONCLUIDA, rotulo: 'Concluída' },
    { valor: StatusExecucao.EM_ANDAMENTO, rotulo: 'Em andamento' },
    { valor: StatusExecucao.FALHA, rotulo: 'Falha' },
    { valor: StatusExecucao.CANCELADA, rotulo: 'Cancelada' },
  ];
  opcoesModo: StyledSelectOption[] = [
    { valor: 'TODOS', rotulo: 'Todos os Modos' },
    { valor: ModoExecucao.SEQUENCIAL, rotulo: 'Sequencial' },
    { valor: ModoExecucao.PARALELO, rotulo: 'Paralelo' },
  ];

  filtroForm = this.fb.nonNullable.group({
    status: 'TODOS' as StatusExecucao | 'TODOS',
    modo: 'TODOS' as ModoExecucao | 'TODOS',
  });

  ngOnInit(): void {
    this.carregar();
    this.filtroForm.valueChanges.subscribe(() => this.carregar());
  }

  carregar(): void {
    this.carregando.set(true);
    const { status, modo } = this.filtroForm.getRawValue();
    this.analysisService.listarHistorico({ status, modo }).subscribe({
      next: (lista) => {
        this.execucoes.set(lista);
        this.erro.set(null);
        this.carregando.set(false);
      },
      error: () => {
        this.execucoes.set([]);
        this.erro.set('Não foi possível carregar o histórico de execuções.');
        this.carregando.set(false);
      },
    });
  }

  excluir(execution: ExecucaoAnalise): void {
    if (
      execution.status === StatusExecucao.PENDENTE ||
      execution.status === StatusExecucao.EM_ANDAMENTO ||
      this.excluindoId() !== null
    ) {
      return;
    }
    const confirmado = window.confirm(
      `Excluir a execução #${execution.id_execucao}? Os resultados, as métricas e qualquer relatório de benchmark relacionado também serão removidos. O dataset e suas transações serão mantidos.`
    );
    if (!confirmado) return;

    this.excluindoId.set(execution.id_execucao);
    this.erro.set(null);
    this.sucesso.set(null);
    this.analysisService.remover(execution.id_execucao).subscribe({
      next: () => {
        this.execucoes.update((lista) =>
          lista.filter((item) => item.id_execucao !== execution.id_execucao)
        );
        this.sucesso.set(
          `Execução #${execution.id_execucao} excluída. O dataset foi mantido para novos testes.`
        );
        this.excluindoId.set(null);
      },
      error: (error: unknown) => {
        this.excluindoId.set(null);
        this.erro.set(
          error instanceof HttpErrorResponse && error.status === 409
            ? 'A execução ainda está em andamento e não pode ser excluída.'
            : 'Não foi possível excluir a execução. Atualize a página e tente novamente.'
        );
      },
    });
  }
}
