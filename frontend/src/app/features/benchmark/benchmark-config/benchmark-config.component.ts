import { Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { DatasetService } from '../../../core/services/dataset.service';
import { BenchmarkService } from '../../../core/services/benchmark.service';
import { Dataset, ModeloDeteccao } from '../../../core/models/dataset.model';
import {
  BenchmarkConfiguracao,
} from '../../../core/models/benchmark.model';
import { OpenCLCapabilities, OpenCLDevice } from '../../../core/models/opencl.model';
import { OpenClDeviceService } from '../../../core/services/opencl-device.service';
import { StyledSelectComponent, StyledSelectOption } from '../../../shared/components/styled-select/styled-select.component';

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
          <p class="page-subtitle">Execute em modo sequencial ou compare o paralelo com a referência sequencial.</p>
        </div>
      </header>

      <div class="df-card cartao">
        <label class="df-label">Dataset Base</label>
        @if (carregandoDatasets()) {
          <p class="estado-dataset" role="status">Carregando datasets…</p>
        } @else if (opcoesDataset().length) {
          <app-styled-select [formControl]="datasetControl" ariaLabel="Dataset base" [opcoes]="opcoesDataset()" />
        } @else {
          <p class="estado-dataset">Nenhum dataset disponível. Importe um CSV para executar o benchmark.</p>
        }

        <hr class="separador" />

        <label class="df-label">Modo de execução</label>
        <div class="opcoes-modo" role="radiogroup" aria-label="Modo de execução do benchmark">
          <label class="opcao-modo">
            <input type="radio" name="modo-benchmark" value="SEQUENCIAL" [checked]="modoSelecionado() === 'SEQUENCIAL'" (change)="selecionarModo('SEQUENCIAL')" />
            <span>Sequencial</span>
            <small>Executa a referência sequencial.</small>
          </label>
          <label class="opcao-modo">
            <input type="radio" name="modo-benchmark" value="PARALELO" [checked]="modoSelecionado() === 'PARALELO'" (change)="selecionarModo('PARALELO')" />
            <span>Paralelo</span>
            <small>Compara o resultado paralelo com a referência sequencial.</small>
          </label>
        </div>

        @if (modoSelecionado() === 'PARALELO') {
          <div class="caixa-workers">
            @if (capacidades(); as info) {
              <label class="seletor-dispositivo">
                <span>Dispositivo de processamento</span>
                <select
                  [value]="tipoDispositivoSelecionado()"
                  (change)="selecionarDispositivo($event)"
                  aria-label="Dispositivo de processamento"
                >
                  @for (dispositivo of info.dispositivos; track dispositivo.tipo) {
                    <option [value]="dispositivo.tipo">
                      {{ dispositivo.tipo === 'CPU' ? 'Processador (CPU)' : 'Placa de vídeo (GPU)' }}
                    </option>
                  }
                  @if (!tipoDispositivoDisponivel('CPU')) {
                    <option value="CPU" disabled>Processador (CPU) — OpenCL indisponível</option>
                  }
                  @if (!tipoDispositivoDisponivel('GPU')) {
                    <option value="GPU" disabled>Placa de vídeo (GPU) — OpenCL indisponível</option>
                  }
                </select>
              </label>
            }
            <div class="linha-slider">
              <span>Workers por grupo: {{ workersSelecionados() }}</span>
              @if (dispositivoSelecionado(); as dispositivo) {
                <span class="nucleos">{{ dispositivo.nome }} · máximo {{ dispositivo.max_workers }}</span>
              } @else if (carregandoCapacidades()) {
                <span class="nucleos">Detectando recursos OpenCL…</span>
              }
            </div>
            <input
              type="range"
              min="1"
              [max]="dispositivoSelecionado()?.max_workers ?? 1"
              [value]="workersSelecionados()"
              class="slider"
              [disabled]="!dispositivoSelecionado()"
              aria-label="Quantidade de workers para comparação paralela"
              (input)="atualizarWorkers($event)"
            />
            <small class="ajuda-workers">Escolha entre processador ou GPU OpenCL disponível no backend. O benchmark executará primeiro a referência sequencial e depois a configuração paralela selecionada.</small>
          </div>
        }

        @if (erro()) {
          <div class="df-alerta df-alerta-erro" style="margin-top:16px" role="alert">
            <span>{{ erro() }}</span>
            <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="erro.set(null)">×</button>
          </div>
        }

        <div class="acoes">
          <button class="df-btn df-btn-roxo" (click)="executarBateria()" [disabled]="carregando() || (modoSelecionado() === 'PARALELO' && !capacidades())">
            @if (carregando()) {
              <span class="df-spinner" aria-hidden="true"></span> Executando bateria…
            } @else {
              Executar Benchmark
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
      .estado-dataset { padding: 10px 12px; border: 1px solid var(--cor-borda); border-radius: 8px; color: var(--cor-texto-suave); font-size: 13px; }
      .opcoes-modo { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
      .opcao-modo { display: grid; grid-template-columns: 18px 1fr; align-items: start; gap: 4px 9px; padding: 13px; border: 1px solid var(--cor-borda); border-radius: 8px; background: var(--cor-superficie); color: var(--cor-texto); cursor: pointer; }
      .opcao-modo:has(input:checked) { border-color: var(--cor-primaria); background: var(--cor-superficie-suave); }
      .opcao-modo input { grid-row: span 2; margin: 2px 0 0; accent-color: var(--cor-primaria); }
      .opcao-modo span { font-size: 13px; font-weight: 600; }
      .opcao-modo small { color: var(--cor-texto-suave); font-size: 11px; line-height: 1.45; }
      .caixa-workers { background: var(--cor-superficie-suave); color: var(--cor-texto); border: 1px solid var(--cor-borda); border-radius: 8px; padding: 14px 16px; }
      .caixa-workers { margin-top: 16px; }
      .seletor-dispositivo { display: grid; gap: 7px; margin-bottom: 14px; color: var(--cor-texto); font-size: 13px; font-weight: 600; }
      .seletor-dispositivo select { width: 100%; padding: 9px 11px; border: 1px solid var(--cor-borda); border-radius: 7px; background: var(--cor-superficie); color: var(--cor-texto); font: inherit; }
      .linha-slider { display: flex; justify-content: space-between; gap: 12px; font-size: 13.5px; margin-bottom: 8px; }
      .nucleos, .ajuda-workers { color: var(--cor-texto-suave); }
      .slider { width: 100%; accent-color: var(--cor-primaria); }
      .ajuda-workers { display: block; margin-top: 7px; font-size: 11px; }
      .acoes { display: flex; justify-content: flex-end; margin-top: 28px; }
      @media (max-width: 560px) { .opcoes-modo { grid-template-columns: 1fr; } }
    `,
  ],
})
export class BenchmarkConfigComponent implements OnInit {
  private fb = inject(FormBuilder);
  private datasetService = inject(DatasetService);
  private benchmarkService = inject(BenchmarkService);
  private openClDeviceService = inject(OpenClDeviceService);
  private router = inject(Router);

  datasets = signal<Dataset[]>([]);
  opcoesDataset = signal<StyledSelectOption[]>([]);
  modelos = signal<ModeloDeteccao[]>([]);
  capacidades = signal<OpenCLCapabilities | null>(null);
  tipoDispositivoSelecionado = signal<'CPU' | 'GPU' | null>(null);
  carregandoCapacidades = signal(true);
  workersSelecionados = signal(1);
  modoSelecionado = signal<'SEQUENCIAL' | 'PARALELO'>('SEQUENCIAL');
  datasetControl = this.fb.nonNullable.control(0);
  carregando = signal(false);
  carregandoDatasets = signal(true);
  erro = signal<string | null>(null);

  ngOnInit(): void {
    this.openClDeviceService.obterCapacidades().pipe(
      finalize(() => this.carregandoCapacidades.set(false))
    ).subscribe({
      next: (capacidades) => {
        this.capacidades.set(capacidades);
        const selected = capacidades.dispositivos.find((device) => device.tipo === 'GPU')
          ?? capacidades.dispositivos[0];
        this.tipoDispositivoSelecionado.set(selected?.tipo ?? null);
        this.workersSelecionados.set(Math.min(4, selected?.max_workers ?? 1));
      },
      error: (error: { error?: { detail?: unknown } }) => this.erro.set(
        typeof error.error?.detail === 'string'
          ? error.error.detail
          : 'Não foi possível detectar os limites do dispositivo OpenCL do backend.'
      ),
    });
    this.datasetService.listar().pipe(
      finalize(() => this.carregandoDatasets.set(false))
    ).subscribe({
      next: (lista) => {
        this.datasets.set(lista);
        this.opcoesDataset.set(lista.map((ds) => ({
          valor: String(ds.id_dataset),
          rotulo: `${ds.nome} (${ds.total_registros.toLocaleString('pt-BR')} registros)`,
        })));
        if (lista[0]) this.datasetControl.setValue(lista[0].id_dataset);
      },
      error: () => this.erro.set('Não foi possível carregar os datasets.'),
    });
    this.datasetService.listarModelos().subscribe({
      next: (lista) => this.modelos.set(lista),
      error: () => this.modelos.set([]),
    });
  }

  selecionarModo(modo: 'SEQUENCIAL' | 'PARALELO'): void {
    this.modoSelecionado.set(modo);
  }

  atualizarWorkers(event: Event): void {
    const workers = Number((event.target as HTMLInputElement).value);
    this.workersSelecionados.set(workers);
  }

  dispositivoSelecionado(): OpenCLDevice | undefined {
    return this.capacidades()?.dispositivos.find(
      (device) => device.tipo === this.tipoDispositivoSelecionado()
    );
  }

  tipoDispositivoDisponivel(type: 'CPU' | 'GPU'): boolean {
    return this.capacidades()?.dispositivos.some((device) => device.tipo === type) ?? false;
  }

  selecionarDispositivo(event: Event): void {
    const type = (event.target as HTMLSelectElement).value;
    if (type !== 'CPU' && type !== 'GPU') return;
    this.tipoDispositivoSelecionado.set(type);
    const device = this.dispositivoSelecionado();
    if (device) {
      this.workersSelecionados.update((workers) =>
        Math.min(workers, device.max_workers)
      );
    }
  }

  executarBateria(): void {
    const idModelo = this.modelos()[0]?.id_modelo;
    if (!this.datasetControl.value || !idModelo) {
      this.erro.set('Selecione um dataset com modelo treinado disponível.');
      return;
    }

    const configuracoes: BenchmarkConfiguracao[] = [
      {
        modo_execucao: 'SEQUENCIAL',
        num_workers: 1,
        rotulo: 'Sequencial (Baseline)',
      },
    ];
    if (this.modoSelecionado() === 'PARALELO') {
      configuracoes.push({
        modo_execucao: 'PARALELO',
        num_workers: this.workersSelecionados(),
        tipo_dispositivo: this.tipoDispositivoSelecionado(),
        rotulo: `Paralelo ${this.tipoDispositivoSelecionado()} (${this.workersSelecionados()} workers)`,
      });
    }

    this.carregando.set(true);
    this.erro.set(null);

    this.benchmarkService
      .executarBateria({ id_dataset: this.datasetControl.value, id_modelo: idModelo, configuracoes })
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (bench) => this.router.navigate(['/benchmark', bench.id_benchmark, 'relatorio']),
        error: (error: { error?: { detail?: unknown } }) => this.erro.set(
          typeof error.error?.detail === 'string'
            ? error.error.detail
            : 'Não foi possível executar o benchmark.'
        ),
      });
  }
}
