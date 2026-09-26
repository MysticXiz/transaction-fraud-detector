import { Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { DatasetService } from '../../../core/services/dataset.service';
import { BenchmarkService } from '../../../core/services/benchmark.service';
import { Dataset, ModeloDeteccao } from '../../../core/models/dataset.model';
import { BenchmarkConfiguracao } from '../../../core/models/benchmark.model';
import { StyledSelectComponent, StyledSelectOption } from '../../../shared/components/styled-select/styled-select.component';

interface OpcaoWorkers {
  workers: number;
  rotulo: string;
  selecionado: boolean;
  fixo: boolean;
}

@Component({
  selector: 'app-benchmark-config',
  standalone: true,
  imports: [ReactiveFormsModule, StyledSelectComponent],
  template: `
    <div class="df-pagina-estreita">
      <header class="page-header">
        <div class="page-header__copy">
          <p class="page-eyebrow">Desempenho</p>
          <h1 class="page-title">Executar Benchmark</h1>
          <p class="page-subtitle">Compare o tempo de execução entre diferentes configurações de paralelismo.</p>
        </div>
      </header>

      <div class="df-card cartao">
        <label class="df-label">Dataset Base</label>
        <app-styled-select [formControl]="datasetControl" [opcoes]="opcoesDataset" />

        <hr class="separador" />

        <label class="df-label">Configurações a comparar</label>
        <div class="lista-opcoes">
          @for (op of opcoes(); track op.workers) {
            <label class="opcao" [class.desabilitada]="op.fixo">
              <input type="checkbox" [checked]="op.selecionado" [disabled]="op.fixo" (change)="alternar(op)" />
              {{ op.rotulo }}
            </label>
          }
        </div>

        @if (erro()) {
          <div class="df-alerta df-alerta-erro" style="margin-top:16px" role="alert">
            <span>{{ erro() }}</span>
            <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="erro.set(null)">×</button>
          </div>
        }

        <div class="acoes">
          <button class="df-btn df-btn-roxo" (click)="executarBateria()" [disabled]="carregando()">
            @if (carregando()) {
              <span class="df-spinner" aria-hidden="true"></span> Executando bateria…
            } @else {
              Executar Bateria Completa
            }
          </button>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      .cartao { width: 100%; }
      .separador { border: none; border-top: 1px solid var(--cor-borda); margin: 24px 0; }
      .lista-opcoes { display: flex; flex-direction: column; gap: 12px; }
      .opcao { display: flex; align-items: center; gap: 10px; font-size: 14px; }
      .opcao.desabilitada { color: var(--cor-texto-suave); }
      .acoes { display: flex; justify-content: flex-end; margin-top: 28px; }
    `,
  ],
})
export class BenchmarkConfigComponent implements OnInit {
  private fb = inject(FormBuilder);
  private datasetService = inject(DatasetService);
  private benchmarkService = inject(BenchmarkService);
  private router = inject(Router);

  datasets = signal<Dataset[]>([]);
  opcoesDataset: StyledSelectOption[] = [];
  modelos = signal<ModeloDeteccao[]>([]);
  datasetControl = this.fb.nonNullable.control(0);
  carregando = signal(false);
  erro = signal<string | null>(null);

  opcoes = signal<OpcaoWorkers[]>([
    { workers: 1, rotulo: 'Sequencial (Baseline Obrigatório)', selecionado: true, fixo: true },
    { workers: 2, rotulo: 'Paralelo (2 workers)', selecionado: true, fixo: false },
    { workers: 4, rotulo: 'Paralelo (4 workers)', selecionado: true, fixo: false },
    { workers: 8, rotulo: 'Paralelo (8 workers)', selecionado: true, fixo: false },
    {
      workers: navigator.hardwareConcurrency || 12,
      rotulo: `Paralelo (${navigator.hardwareConcurrency || 12} workers - Máx)`,
      selecionado: true,
      fixo: false,
    },
  ]);

  ngOnInit(): void {
    this.datasetService.listar().subscribe({
      next: (lista) => {
        this.datasets.set(lista);
        this.opcoesDataset = lista.map((ds) => ({ valor: String(ds.id_dataset), rotulo: `${ds.nome} (${ds.total_registros.toLocaleString('pt-BR')} registros)` }));
        if (lista[0]) this.datasetControl.setValue(lista[0].id_dataset);
      },
      error: () => this.erro.set('Não foi possível carregar os datasets.'),
    });
    this.datasetService.listarModelos().subscribe({
      next: (lista) => this.modelos.set(lista),
      error: () => this.modelos.set([]),
    });
  }

  alternar(opcao: OpcaoWorkers): void {
    if (opcao.fixo) return;
    this.opcoes.update((lista) =>
      lista.map((o) => (o.workers === opcao.workers ? { ...o, selecionado: !o.selecionado } : o))
    );
  }

  executarBateria(): void {
    const idModelo = this.modelos()[0]?.id_modelo;
    if (!this.datasetControl.value || !idModelo) {
      this.erro.set('Selecione um dataset com modelo treinado disponível.');
      return;
    }

    const configuracoes: BenchmarkConfiguracao[] = this.opcoes()
      .filter((o) => o.selecionado)
      .map((o) => ({
        modo_execucao: o.fixo ? 'SEQUENCIAL' : 'PARALELO',
        num_workers: o.workers,
        rotulo: o.rotulo,
      }));

    this.carregando.set(true);
    this.erro.set(null);

    this.benchmarkService
      .executarBateria({ id_dataset: this.datasetControl.value, id_modelo: idModelo, configuracoes })
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (bench) => this.router.navigate(['/benchmark', bench.id_benchmark, 'relatorio']),
        error: () => this.erro.set('Não foi possível executar a bateria de benchmark.'),
      });
  }
}
