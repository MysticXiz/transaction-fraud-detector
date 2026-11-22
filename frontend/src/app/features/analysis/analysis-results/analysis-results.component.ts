import { Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { AnalysisService, ResultadosFiltro } from '../../../core/services/analysis.service';
import { ExecucaoAnalise, MetricaExecucao, ResultadoDeteccao } from '../../../core/models/analise.model';

@Component({
  selector: 'app-analysis-results',
  standalone: true,
  imports: [RouterLink, DecimalPipe, ReactiveFormsModule],
  template: `
    <header class="page-header">
      <div class="page-header__copy">
        <p class="page-eyebrow">Resultados da análise</p>
        <h1 class="page-title">Execução #{{ idExecucao }}</h1>
      @if (execucao(); as ex) {
        <p class="page-subtitle">
          {{ ex.modo_execucao === 'SEQUENCIAL' ? 'Sequencial' : 'Paralelo · work-group solicitado ' + ex.work_group_size }}
        </p>
      }
      </div>
      @if (execucao()?.status === 'CONCLUIDA' && !carregando() && !erro()) {
        <div class="page-header__actions">
          <a class="df-btn df-btn-secundario" [href]="urlExportacao('csv')" download>Exportar CSV</a>
          <a class="df-btn df-btn-secundario" [href]="urlExportacao('json')" download>Exportar JSON</a>
        </div>
      }
    </header>

    @if (erro()) {
      <div class="df-alerta df-alerta-erro" role="alert">
        <span>{{ erro() }}</span>
        <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="erro.set(null)">×</button>
      </div>
    }

    <div class="grid-resumo">
      <div class="df-card mini"><p class="rotulo">Analisadas</p><p class="valor">{{ execucao()?.total_analisadas | number: '1.0-0' : 'pt-BR' }}</p></div>
      <div class="df-card mini destaque"><p class="rotulo">Suspeitas</p><p class="valor cor-erro">{{ execucao()?.total_suspeitas | number: '1.0-0' : 'pt-BR' }}</p></div>
      <div class="df-card mini"><p class="rotulo">Taxa de suspeitas</p><p class="valor">{{ taxaSuspeicao() }}%</p></div>
      <div class="df-card mini"><p class="rotulo">Tempo total da análise</p><p class="valor">{{ execucao()?.tempo_total_s | number: '1.2-2' : 'pt-BR' }} s</p></div>
      <div class="df-card mini"><p class="rotulo">Transações por segundo</p><p class="valor">{{ metrica()?.throughput_tps | number: '1.0-0' : 'pt-BR' }}</p></div>
    </div>

    @if (metrica(); as m) {
      <div class="grid-resumo">
        <div class="df-card mini"><p class="rotulo">Leitura do banco</p><p class="valor">{{ m.tempo_leitura_s | number: '1.2-2' : 'pt-BR' }} s</p></div>
        <div class="df-card mini"><p class="rotulo">Pré-processamento</p><p class="valor">{{ m.tempo_preproc_s | number: '1.2-2' : 'pt-BR' }} s</p></div>
        <div class="df-card mini" title="Tempo acumulado de cálculo dos scores. As novas análises OpenCL incluem o kernel e as cópias de entrada e saída. Execuções antigas podem ter registrado só a espera pela coleta.">
          <p class="rotulo">Inferência</p><p class="valor">{{ m.tempo_inferencia_s | number: '1.2-3' : 'pt-BR' }} s</p>
        </div>
        <div class="df-card mini" title="Tempo total menos leitura, pré-processamento e inferência. Inclui treinamento, gravação e outras esperas que não se sobrepõem às etapas medidas.">
          <p class="rotulo">Tempo restante da análise</p><p class="valor">{{ m.tempo_overhead_s | number: '1.2-2' : 'pt-BR' }} s</p>
        </div>
        <div class="df-card mini" title="Maior valor de memória residente do processo do backend observado durante a análise.">
          <p class="rotulo">Pico de memória do backend</p><p class="valor">{{ m.memoria_pico_mb | number: '1.0-0' : 'pt-BR' }} MiB</p>
        </div>
      </div>
    }

    <div class="df-card sem-padding">
      <form [formGroup]="filtroForm" (ngSubmit)="aplicarFiltro()" class="barra-filtros">
        <label for="escore-minimo">Escore mínimo</label>
        <input id="escore-minimo" class="df-input filtro-input" type="number" min="0" step="any" formControlName="escoreMinimo" />
        <label for="valor-minimo">Valor mínimo</label>
        <input id="valor-minimo" class="df-input filtro-input" type="number" min="0" step="any" formControlName="valorMinimo" />
        <label for="suspeita">Classificação</label>
        <select id="suspeita" class="df-input" formControlName="classificacao">
          <option value="todas">Todas</option>
          <option value="suspeitas">Suspeitas</option>
          <option value="regulares">Regulares</option>
        </select>
        <button type="submit" class="df-btn df-btn-secundario">Aplicar</button>
      </form>

      @if (carregando()) {
        <p class="rodape-tabela" role="status">Carregando resultados…</p>
      } @else if (resultados().length) {
        <table class="df-table">
          <thead>
            <tr>
              <th>ID da Transação</th>
              <th>Escore</th>
              <th>Valor ($)</th>
              <th>Classificação</th>
              <th style="text-align:right">Ação</th>
            </tr>
          </thead>
          <tbody>
            @for (r of resultados(); track r.id_resultado) {
              <tr>
                <td>{{ r.id_transacao }}</td>
                <td class="cor-erro" style="font-weight:700">{{ r.score_anomalia | number: '1.4-4' : 'pt-BR' }}</td>
                <td>{{ r.valor | number: '1.2-2' : 'pt-BR' }}</td>
                <td>{{ r.is_suspeita ? 'Suspeita' : 'Regular' }}</td>
                <td style="text-align:right">
                  <a class="df-link" [routerLink]="['/analises', idExecucao, 'resultados', r.id_transacao]">
                    Detalhes
                  </a>
                </td>
              </tr>
            }
          </tbody>
        </table>
      } @else if (execucao() && !erro()) {
        <div class="df-estado sem-borda">
          <span class="df-estado-icone" aria-hidden="true">▤</span>
          <h2>Nenhum resultado encontrado</h2>
          <p>Confira os filtros ou consulte novamente depois que a análise terminar.</p>
        </div>
      }

      @if (total() > 0 && !carregando() && !erro()) {
        <nav class="rodape-tabela" aria-label="Paginação de resultados">
          <button type="button" class="df-btn df-btn-secundario" [disabled]="pagina() <= 1" (click)="carregar(pagina() - 1)">Anterior</button>
          <span>Página {{ pagina() }} de {{ totalPaginas() }} · {{ total() | number: '1.0-0' : 'pt-BR' }} resultados</span>
          <button type="button" class="df-btn df-btn-secundario" [disabled]="pagina() >= totalPaginas()" (click)="carregar(pagina() + 1)">Próxima</button>
        </nav>
      }
    </div>
  `,
  styles: [
    `
      .grid-resumo { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; margin-bottom: 20px; }
      .mini { padding: 16px 18px; }
      .mini .rotulo { font-size: 12.5px; color: var(--cor-texto-suave); margin-bottom: 4px; }
      .mini .valor { font-size: 20px; font-weight: 700; }
      .destaque { background: color-mix(in srgb, var(--cor-erro-bg) 35%, var(--cor-superficie)); }
      .cor-erro { color: var(--cor-erro-texto); }
      .sem-padding { padding: 0; overflow: hidden; }
      .barra-filtros { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 16px 24px; border-bottom: 1px solid var(--cor-borda); font-size: 13.5px; }
      .filtro-input { width: 100px; }
      .df-table th, .df-table td { padding-left: 24px; padding-right: 24px; }
      .rodape-tabela { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 18px 24px; }
      .sem-borda { border: 0; border-radius: 0; padding: 48px 20px; }
      @media (max-width: 900px) { .grid-resumo { grid-template-columns: repeat(2, 1fr); } }
    `,
  ],
})
export class AnalysisResultsComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private analysisService = inject(AnalysisService);
  private fb = inject(FormBuilder);
  private destroyRef = inject(DestroyRef);
  private consulta?: Subscription;
  private filtro: ResultadosFiltro = {};
  private readonly tamanhoPagina = 25;

  idExecucao = 0;
  execucao = signal<ExecucaoAnalise | null>(null);
  metrica = signal<MetricaExecucao | null>(null);
  resultados = signal<ResultadoDeteccao[]>([]);
  erro = signal<string | null>(null);
  carregando = signal(false);
  pagina = signal(1);
  total = signal(0);
  totalPaginas = computed(() => Math.ceil(this.total() / this.tamanhoPagina));

  filtroForm = this.fb.nonNullable.group({
    escoreMinimo: [null as number | null],
    valorMinimo: [null as number | null],
    classificacao: ['todas'],
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

  carregar(numeroPagina = 1): void {
    this.consulta?.unsubscribe();
    this.carregando.set(true);
    this.erro.set(null);
    this.consulta = this.analysisService
      .obterResultados(this.idExecucao, {
        ...this.filtro,
        pagina: numeroPagina,
        tamanhoPagina: this.tamanhoPagina,
      })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: (pagina) => {
          this.pagina.set(pagina.pagina);
          this.total.set(pagina.total);
          this.execucao.set(pagina.execucao);
          this.metrica.set(pagina.metrica);
          this.resultados.set(pagina.itens);
          this.carregando.set(false);
        },
        error: () => {
          this.execucao.set(null);
          this.metrica.set(null);
          this.resultados.set([]);
          this.total.set(0);
          this.carregando.set(false);
          this.erro.set('Não foi possível carregar os resultados desta execução.');
        },
      });
  }

  aplicarFiltro(): void {
    if (this.filtroForm.invalid) return;
    const { escoreMinimo, valorMinimo, classificacao } = this.filtroForm.getRawValue();
    this.filtro = {
      escoreMinimo: escoreMinimo ?? undefined,
      valorMinimo: valorMinimo ?? undefined,
      suspeita: classificacao === 'todas' ? undefined : classificacao === 'suspeitas',
    };
    this.carregar();
  }

  urlExportacao(formato: 'csv' | 'json'): string {
    return this.analysisService.urlExportacao(this.idExecucao, formato, this.filtro);
  }
}
