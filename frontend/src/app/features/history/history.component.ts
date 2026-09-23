import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { AnalysisService } from '../../core/services/analysis.service';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ExecucaoAnalise } from '../../core/models/analise.model';
import { ModoExecucao, StatusExecucao } from '../../core/models/enums';

@Component({
  selector: 'app-history',
  standalone: true,
  imports: [RouterLink, DecimalPipe, ReactiveFormsModule, StatusBadgeComponent],
  template: `
    <h1 class="titulo-pagina">Histórico de Execuções</h1>

    <div class="df-card sem-padding">
      <form [formGroup]="filtroForm" class="barra-filtros">
        <select class="df-select filtro-select" formControlName="status">
          <option value="TODOS">Todos os Status</option>
          <option [value]="Status.CONCLUIDA">Concluída</option>
          <option [value]="Status.EM_ANDAMENTO">A decorrer</option>
          <option [value]="Status.FALHA">Falha</option>
          <option [value]="Status.CANCELADA">Cancelada</option>
        </select>
        <select class="df-select filtro-select" formControlName="modo">
          <option value="TODOS">Todos os Modos</option>
          <option [value]="Modo.SEQUENCIAL">Sequencial</option>
          <option [value]="Modo.PARALELO">Paralelo</option>
        </select>
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
      .sem-padding { padding: 0; overflow: hidden; }
      .barra-filtros { display: flex; gap: 12px; padding: 18px 24px; border-bottom: 1px solid var(--cor-borda); }
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
