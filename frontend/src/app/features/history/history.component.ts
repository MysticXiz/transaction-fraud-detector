import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { AnalysisService } from '../../core/services/analysis.service';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ExecucaoAnalise } from '../../core/models/analise.model';
import { ModoExecucao, StatusExecucao } from '../../core/models/enums';
import { StyledSelectComponent, StyledSelectOption } from '../../shared/components/styled-select/styled-select.component';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, DecimalPipe, ReactiveFormsModule, StatusBadgeComponent, StyledSelectComponent],
  template: `
    <div class="cabecalho-secao">
      <p class="eyebrow">Acompanhamento</p>
      <h1 class="titulo-pagina">Histórico de Execuções</h1>
    </div>

    <div class="df-card sem-padding">
      <form [formGroup]="filtroForm" class="barra-filtros">
        <app-styled-select class="filtro-select" formControlName="status" [opcoes]="opcoesStatus" />
        <app-styled-select class="filtro-select" formControlName="modo" [opcoes]="opcoesModo" />
      </form>

      @if (execucoes().length) {
        <table class="df-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Dataset</th>
              <th>Modo</th>
              <th>Status</th>
              <th>Tempo</th>
              <th style="text-align:right">Ação</th>
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
                  <a class="df-link" [routerLink]="['/analises', e.id_execucao, 'resultados']">Ver Resultados</a>
                </td>
              </tr>
            }
          </tbody>
        </table>
      } @else {
        <p class="df-vazio">Nenhuma execução encontrada para os filtros selecionados.</p>
      }
    </div>
  `,
  styles: [
    `
      .titulo-pagina { font-size: 26px; font-weight: 700; margin-bottom: 24px; }
      .eyebrow { color: var(--cor-primaria); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 7px; }
      .sem-padding { padding: 0; overflow: visible; }
      .barra-filtros { position: relative; z-index: 2; display: flex; gap: 12px; padding: 18px 24px; border-bottom: 1px solid var(--cor-borda); }
      .filtro-select { width: 180px; }
      .df-table th, .df-table td { padding-left: 24px; padding-right: 24px; }
    `,
  ],
})
export class HistoryComponent implements OnInit {
  private analysisService = inject(AnalysisService);
  private fb = inject(FormBuilder);

  Status = StatusExecucao;
  Modo = ModoExecucao;
  execucoes = signal<ExecucaoAnalise[]>([]);

  opcoesStatus: StyledSelectOption[] = [
    { valor: 'TODOS', rotulo: 'Todos os Status' },
    { valor: StatusExecucao.CONCLUIDA, rotulo: 'Concluída' },
    { valor: StatusExecucao.EM_ANDAMENTO, rotulo: 'A decorrer' },
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
    const { status, modo } = this.filtroForm.getRawValue();
    this.analysisService.listarHistorico({ status, modo }).subscribe({
      next: (lista) => this.execucoes.set(lista),
      error: () => this.execucoes.set([]),
    });
  }
}
