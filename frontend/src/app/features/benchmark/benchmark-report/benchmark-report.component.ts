import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { finalize } from 'rxjs';
import { BenchmarkService } from '../../../core/services/benchmark.service';
import { Benchmark, BenchmarkExecucaoItem } from '../../../core/models/benchmark.model';

@Component({
  selector: 'app-benchmark-report',
  standalone: true,
  imports: [RouterLink, DecimalPipe],
  template: `
    <div class="df-pagina">
      <header class="page-header">
        <div class="page-header__copy">
          <a routerLink="/benchmark" class="page-backlink">← Voltar para Configuração</a>
          <p class="page-eyebrow">Desempenho</p>
          <h1 class="page-title">Relatório de Benchmark</h1>
            @if (benchmark(); as b) {
              <p class="page-subtitle">Dataset: {{ b.dataset_nome }} · {{ b.total_registros | number: '1.0-0' : 'pt-BR' }} registros</p>
            }
        </div>
        <div class="page-header__actions">
          <button class="df-btn df-btn-secundario" (click)="exportarPdf()">Exportar relatório PDF</button>
        </div>
      </header>

      @if (carregando()) {
        <div class="carregando" role="status" aria-live="polite">
          <span class="df-spinner df-spinner-suave" aria-hidden="true"></span>
          <p>Carregando relatório…</p>
        </div>
      } @else if (benchmark(); as b) {
        <div class="grid-graficos">
          <div class="df-card">
            <h2 class="titulo-secao">Curva de Speedup (Real vs Ideal)</h2>
            <svg viewBox="0 0 420 260" class="grafico">
              <line x1="40" y1="220" x2="400" y2="220" stroke="#e5e7eb" />
              <line x1="40" y1="20" x2="40" y2="220" stroke="#e5e7eb" />
              <polyline [attr.points]="linhaIdeal()" fill="none" stroke="#c4b5fd" stroke-width="2" stroke-dasharray="4 4" />
              <polyline [attr.points]="linhaReal()" fill="none" stroke="#7c3aed" stroke-width="2" />
              @for (p of pontosReais(); track p.x) {
                <circle [attr.cx]="p.x" [attr.cy]="p.y" r="5" fill="#7c3aed" />
              }
              @for (item of b.execucoes; track item.id_benchmark_exec; let i = $index) {
                <text [attr.x]="40 + i * (360 / (b.execucoes.length - 1 || 1))" y="238" font-size="11" fill="#6b7280" text-anchor="middle">
                  {{ item.num_workers }}w
                </text>
              }
            </svg>
          </div>

          <div class="df-card">
            <h2 class="titulo-secao">Eficiência (%)</h2>
            <svg viewBox="0 0 420 260" class="grafico">
              @for (item of b.execucoes; track item.id_benchmark_exec; let i = $index) {
                <rect
                  [attr.x]="40 + i * (360 / b.execucoes.length) + 10"
                  [attr.y]="220 - item.eficiencia * 2"
                  [attr.width]="360 / b.execucoes.length - 20"
                  [attr.height]="item.eficiencia * 2"
                  fill="#60a5fa"
                  rx="3"
                />
                <text [attr.x]="40 + i * (360 / b.execucoes.length) + (360 / b.execucoes.length) / 2" y="238" font-size="11" fill="#6b7280" text-anchor="middle">
                  {{ item.num_workers }}w
                </text>
              }
            </svg>
          </div>
        </div>

        <div class="df-card sem-padding">
          <div class="tabela-wrap">
            <table class="df-table">
              <thead>
                <tr>
                  <th>Modo</th>
                  <th>Workers</th>
                  <th>Tempo (s)</th>
                  <th>Speedup</th>
                  <th>Eficiência</th>
                </tr>
              </thead>
              <tbody>
                @for (item of b.execucoes; track item.id_benchmark_exec) {
                  <tr>
                    <td [class.baseline]="item.papel === 'BASELINE'">
                      {{ item.modo_execucao === 'SEQUENCIAL' ? 'Sequencial' : 'Paralelo' }}
                    </td>
                    <td>{{ item.num_workers }}</td>
                    <td>{{ item.tempo_s | number: '1.2-2' : 'pt-BR' }}</td>
                    <td [class.roxo]="item.papel !== 'BASELINE'">{{ item.speedup | number: '1.2-2' : 'pt-BR' }}x</td>
                    <td [class.cor-erro]="item.eficiencia < 75">{{ item.eficiencia | number: '1.1-1' : 'pt-BR' }}%</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </div>
      } @else if (erro()) {
        <div class="df-estado">
          <h2>Não foi possível carregar o relatório</h2>
          <p>{{ erro() }}</p>
          <button class="df-btn df-btn-secundario" type="button" (click)="carregar()">Tentar novamente</button>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .grid-graficos { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
      .titulo-secao { font-size: 15px; font-weight: 700; margin-bottom: 16px; text-align: center; }
      .grafico { width: 100%; height: 240px; }
      .sem-padding { padding: 0; overflow: hidden; }
      .tabela-wrap { overflow-x: auto; }
      .carregando { display: flex; align-items: center; gap: 10px; padding: 24px 4px; color: var(--cor-texto-suave); font-size: 13px; }
      .baseline { color: var(--cor-texto-suave); }
      .roxo { color: var(--cor-roxo); font-weight: 700; }
      .cor-erro { color: var(--cor-erro-texto); }
      @media (max-width: 900px) { .grid-graficos { grid-template-columns: 1fr; } }
    `,
  ],
})
export class BenchmarkReportComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private benchmarkService = inject(BenchmarkService);

  benchmark = signal<Benchmark | null>(null);
  erro = signal<string | null>(null);
  carregando = signal(true);

  pontosReais = computed(() => this.calcularPontos(this.benchmark()?.execucoes ?? []));
  linhaReal = computed(() => this.pontosReais().map((p) => `${p.x},${p.y}`).join(' '));
  linhaIdeal = computed(() => {
    const execs = this.benchmark()?.execucoes ?? [];
    if (!execs.length) return '';
    const maxWorkers = Math.max(...execs.map((e) => e.num_workers));
    return execs
      .map((e, i) => {
        const x = 40 + i * (360 / (execs.length - 1 || 1));
        const idealSpeedup = e.num_workers;
        const y = 220 - (idealSpeedup / maxWorkers) * 190;
        return `${x},${y}`;
      })
      .join(' ');
  });

  private calcularPontos(execs: BenchmarkExecucaoItem[]) {
    if (!execs.length) return [];
    const maxSpeedup = Math.max(...execs.map((e) => e.speedup), 1);
    return execs.map((e, i) => ({
      x: 40 + i * (360 / (execs.length - 1 || 1)),
      y: 220 - (e.speedup / maxSpeedup) * 190,
    }));
  }

  private idBenchmark = 0;

  ngOnInit(): void {
    this.idBenchmark = Number(this.route.snapshot.paramMap.get('id'));
    this.carregar();
  }

  carregar(): void {
    this.erro.set(null);
    this.carregando.set(true);
    this.benchmarkService.obter(this.idBenchmark).pipe(finalize(() => this.carregando.set(false))).subscribe({
      next: (b) => this.benchmark.set(b),
      error: () => this.erro.set('Não foi possível carregar o relatório de benchmark.'),
    });
  }

  exportarPdf(): void {
    const b = this.benchmark();
    if (!b) return;
    this.benchmarkService.exportarPdf(b.id_benchmark).subscribe((blob) => {
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `benchmark-${b.id_benchmark}.pdf`;
      a.click();
      window.URL.revokeObjectURL(url);
    });
  }
}
