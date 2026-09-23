import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { forkJoin } from 'rxjs';
import { StatCardComponent } from '../../shared/components/stat-card/stat-card.component';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { DatasetService } from '../../core/services/dataset.service';
import { AnalysisService } from '../../core/services/analysis.service';
import { ExecucaoAnalise } from '../../core/models/analise.model';
import { StatusExecucao } from '../../core/models/enums';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [RouterLink, StatCardComponent, StatusBadgeComponent],
  template: `
    <div class="cabecalho">
      <h1>Visão Geral</h1>
      <div class="acoes">
        <a routerLink="/datasets/importar" class="df-btn df-btn-secundario">Importar Dataset</a>
        <a routerLink="/analises/nova" class="df-btn df-btn-primary">Nova Análise</a>
      </div>
    </div>

    <div class="grid-cards">
      <app-stat-card rotulo="Datasets" [valor]="totalDatasets()" />
      <app-stat-card rotulo="Análises" [valor]="totalAnalises()" />
      <app-stat-card rotulo="Suspeitas" [valor]="totalSuspeitas()" />
      <a routerLink="/benchmark" class="card-speedup">
        <app-stat-card rotulo="Speedup (ver Benchmark)" [valor]="melhorSpeedupTexto()" />
      </a>
    </div>

    <div class="grid-inferior">
      <div class="df-card">
        <h2 class="titulo-secao">Últimas Execuções por Tempo (s)</h2>
        @if (execucoesGrafico().length) {
          <svg [attr.viewBox]="'0 0 ' + larguraSvg() + ' 220'" class="grafico">
            @for (item of execucoesGrafico(); track item.id_execucao; let i = $index) {
              <rect
                [attr.x]="i * 76 + 16"
                [attr.y]="200 - alturaBarra(item.tempo_total_s)"
                width="44"
                [attr.height]="alturaBarra(item.tempo_total_s)"
                [attr.fill]="i === execucoesGrafico().length - 1 ? '#2563eb' : '#93c5fd'"
                rx="3"
              />
              <text [attr.x]="i * 76 + 38" y="216" text-anchor="middle" font-size="12" fill="#6b7280">
                #{{ item.id_execucao }}
              </text>
            }
          </svg>
        } @else {
          <p class="df-vazio">Nenhuma execução registrada ainda.</p>
        }
      </div>

      <div class="df-card">
        <h2 class="titulo-secao">Execuções Recentes</h2>
        @if (execucoesRecentes().length) {
          <ul class="lista-execucoes">
            @for (exec of execucoesRecentes(); track exec.id_execucao) {
              <li>
                <a [routerLink]="['/analises', exec.id_execucao, 'resultados']">
                  #{{ exec.id_execucao }} - {{ exec.dataset_nome ?? 'dataset' }}
                </a>
                <app-status-badge [status]="exec.status" />
              </li>
            }
          </ul>
        } @else {
          <p class="df-vazio">Nenhuma análise executada.</p>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .cabecalho { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
      .cabecalho h1 { font-size: 26px; font-weight: 700; }
      .acoes { display: flex; gap: 10px; }
      .grid-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
      .grid-inferior { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; }
      .card-speedup { display: block; }
      .titulo-secao { font-size: 16px; font-weight: 700; margin-bottom: 18px; }
      .grafico { width: 100%; height: 220px; }
      .lista-execucoes { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 14px; }
      .lista-execucoes li { display: flex; justify-content: space-between; align-items: center; font-size: 13.5px; }
      .lista-execucoes a { color: var(--cor-texto); font-weight: 500; }
      .lista-execucoes a:hover { color: var(--cor-primaria); }
      @media (max-width: 900px) {
        .grid-cards { grid-template-columns: repeat(2, 1fr); }
        .grid-inferior { grid-template-columns: 1fr; }
      }
    `,
  ],
})
export class DashboardComponent implements OnInit {
  private datasetService = inject(DatasetService);
  private analysisService = inject(AnalysisService);

  private execucoes = signal<ExecucaoAnalise[]>([]);
  private totalDatasetsSignal = signal(0);

  totalDatasets = computed(() => this.totalDatasetsSignal());
  totalAnalises = computed(() => this.execucoes().length);
  totalSuspeitas = computed(() => this.execucoes().reduce((soma, e) => soma + (e.total_suspeitas ?? 0), 0));

  execucoesRecentes = computed(() => this.execucoes().slice(0, 5));
  execucoesGrafico = computed(() => this.execucoes().slice(0, 5).reverse());

  melhorSpeedupTexto = computed(() => '—');

  larguraSvg = computed(() => Math.max(this.execucoesGrafico().length * 76 + 16, 76));

  ngOnInit(): void {
    forkJoin({
      datasets: this.datasetService.listar(),
      execucoes: this.analysisService.listarHistorico(),
    }).subscribe({
      next: ({ datasets, execucoes }) => {
        this.totalDatasetsSignal.set(datasets.length);
        this.execucoes.set(
          [...execucoes]
            .filter((e) => e.status === StatusExecucao.CONCLUIDA || e.status === StatusExecucao.EM_ANDAMENTO)
            .sort((a, b) => b.id_execucao - a.id_execucao)
        );
      },
      error: () => {
        this.totalDatasetsSignal.set(0);
        this.execucoes.set([]);
      },
    });
  }

  alturaBarra(tempo?: number): number {
    if (!tempo) return 4;
    const maximo = Math.max(...this.execucoesGrafico().map((e) => e.tempo_total_s ?? 0), 1);
    return Math.max((tempo / maximo) * 180, 4);
  }
}
