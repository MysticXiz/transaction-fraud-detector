import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { AnalysisService } from '../../../core/services/analysis.service';
import { ExecucaoAnalise, MetricaExecucao, ResultadoDeteccao } from '../../../core/models/analise.model';

@Component({
  selector: 'app-analysis-results',
  standalone: true,
  imports: [RouterLink, DecimalPipe, ReactiveFormsModule],
  template: `
    <div class="cabecalho">
      <h1>Execução #{{ idExecucao }}</h1>
      @if (execucao(); as ex) {
        <p class="subtitulo">
          {{ ex.modo_execucao === 'SEQUENCIAL' ? 'Sequencial' : 'Paralelo · ' + ex.num_workers + ' workers' }}
        </p>
      }
    </div>

    <div class="grid-resumo">
      <div class="df-card mini"><p class="rotulo">Analisadas</p><p class="valor">{{ execucao()?.total_analisadas | number: '1.0-0' : 'pt-BR' }}</p></div>
      <div class="df-card mini destaque"><p class="rotulo">Suspeitas</p><p class="valor cor-erro">{{ execucao()?.total_suspeitas | number: '1.0-0' : 'pt-BR' }}</p></div>
      <div class="df-card mini"><p class="rotulo">Taxa</p><p class="valor">{{ taxaSuspeicao() }}%</p></div>
      <div class="df-card mini"><p class="rotulo">Tempo</p><p class="valor">{{ execucao()?.tempo_total_s | number: '1.2-2' : 'pt-BR' }} s</p></div>
      <div class="df-card mini"><p class="rotulo">Throughput</p><p class="valor">{{ metrica()?.throughput_tps | number: '1.0-0' : 'pt-BR' }}/s</p></div>
    </div>

    <div class="df-card sem-padding">
      <form [formGroup]="filtroForm" (ngSubmit)="aplicarFiltro()" class="barra-filtros">
        <label>Escore &gt;</label>
        <input class="df-input filtro-input" type="number" step="0.01" formControlName="escoreMinimo" />
        <label>Valor &gt;</label>
        <input class="df-input filtro-input" type="number" formControlName="valorMinimo" />
        <button type="submit" class="df-btn df-btn-secundario">Aplicar</button>
      </form>

      @if (resultados().length) {
        <table class="df-table">
          <thead>
            <tr>
              <th>ID da Transação</th>
              <th>Escore</th>
              <th>Valor ($)</th>
              <th style="text-align:right">Ação</th>
            </tr>
          </thead>
          <tbody>
            @for (r of resultados(); track r.id_resultado) {
              <tr>
                <td>{{ r.id_transacao }}</td>
                <td class="cor-erro" style="font-weight:700">{{ r.score_anomalia | number: '1.4-4' : 'pt-BR' }}</td>
                <td>{{ r.valor | number: '1.2-2' : 'pt-BR' }}</td>
                <td style="text-align:right">
                  <a class="df-link" [routerLink]="['/analises', idExecucao, 'resultados', r.id_transacao]">
                    Detalhes
                  </a>
                </td>
              </tr>
            }
          </tbody>
        </table>
      } @else {
        <p class="df-vazio">Nenhuma transação suspeita para os filtros aplicados.</p>
      }

      <div class="rodape-tabela">
        <button class="df-btn df-btn-secundario" (click)="exportar('csv')">Exportar CSV</button>
        <button class="df-btn df-btn-secundario" (click)="exportar('json')">Exportar JSON</button>
      </div>
    </div>
  `,
  styles: [
    `
      .cabecalho { margin-bottom: 20px; }
      .cabecalho h1 { font-size: 24px; font-weight: 700; }
      .subtitulo { color: var(--cor-texto-suave); font-size: 13.5px; margin-top: 4px; }
      .grid-resumo { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 20px; }
      .mini { padding: 16px 18px; }
      .mini .rotulo { font-size: 12.5px; color: var(--cor-texto-suave); margin-bottom: 4px; }
      .mini .valor { font-size: 20px; font-weight: 700; }
      .destaque { background: #fef2f2; }
      .cor-erro { color: var(--cor-erro-texto); }
      .sem-padding { padding: 0; overflow: hidden; }
      .barra-filtros { display: flex; align-items: center; gap: 10px; padding: 16px 24px; border-bottom: 1px solid var(--cor-borda); font-size: 13.5px; }
      .filtro-input { width: 100px; }
      .df-table th, .df-table td { padding-left: 24px; padding-right: 24px; }
      .rodape-tabela { display: flex; gap: 10px; padding: 18px 24px; }
      @media (max-width: 900px) { .grid-resumo { grid-template-columns: repeat(2, 1fr); } }
    `,
  ],
})
export class AnalysisResultsComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private analysisService = inject(AnalysisService);
  private fb = inject(FormBuilder);

  idExecucao = 0;
  execucao = signal<ExecucaoAnalise | null>(null);
  metrica = signal<MetricaExecucao | null>(null);
  resultados = signal<ResultadoDeteccao[]>([]);

  filtroForm = this.fb.nonNullable.group({
    escoreMinimo: [null as number | null],
    valorMinimo: [null as number | null],
  });

  taxaSuspeicao(): string {
    const ex = this.execucao();
    if (!ex || !ex.total_analisadas) return '0,000';
    return ((ex.total_suspeitas / ex.total_analisadas) * 100).toFixed(3).replace('.', ',');
  }

  ngOnInit(): void {
    this.idExecucao = Number(this.route.snapshot.paramMap.get('id'));
    this.carregar();
  }

  carregar(): void {
    const { escoreMinimo, valorMinimo } = this.filtroForm.getRawValue();
    this.analysisService
      .obterResultados(this.idExecucao, {
        escoreMinimo: escoreMinimo ?? undefined,
        valorMinimo: valorMinimo ?? undefined,
      })
      .subscribe({
        next: (pagina) => {
          this.execucao.set(pagina.execucao);
          this.metrica.set(pagina.metrica);
          this.resultados.set(pagina.itens);
        },
        error: () => {
          this.execucao.set(null);
          this.resultados.set([]);
        },
      });
  }

  aplicarFiltro(): void {
    this.carregar();
  }

  exportar(formato: 'csv' | 'json'): void {
    this.analysisService.exportarResultados(this.idExecucao, formato).subscribe((blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `execucao-${this.idExecucao}-resultados.${formato}`;
      a.click();
      window.URL.revokeObjectURL(url);
    });
  }
}
