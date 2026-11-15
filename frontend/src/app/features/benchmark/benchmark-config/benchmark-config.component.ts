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
import {
  OpenCLCapabilities,
  OpenCLCalibrationResult,
  OpenCLDevice,
} from '../../../core/models/opencl.model';
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
          <p class="page-subtitle">Execute uma comparação completa ou somente o modo paralelo.</p>
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

        <label class="df-label">Tipo de benchmark</label>
        <div class="opcoes-modo" role="radiogroup" aria-label="Tipo de benchmark">
          <label class="opcao-modo">
            <input type="radio" name="tipo-benchmark" value="COMPARATIVO" [checked]="tipoBenchmarkSelecionado() === 'COMPARATIVO'" (change)="selecionarTipoBenchmark('COMPARATIVO')" />
            <span>Comparativo</span>
            <small>Executa o sequencial como baseline e depois o paralelo.</small>
          </label>
          <label class="opcao-modo">
            <input type="radio" name="tipo-benchmark" value="PARALELO_APENAS" [checked]="tipoBenchmarkSelecionado() === 'PARALELO_APENAS'" (change)="selecionarTipoBenchmark('PARALELO_APENAS')" />
            <span>Somente paralelo</span>
            <small>Executa apenas a configuração OpenCL selecionada.</small>
          </label>
        </div>

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
              <span>Tamanho do work-group: {{ workGroupSelecionado() }}</span>
              @if (dispositivoSelecionado(); as dispositivo) {
                <span class="nucleos">{{ dispositivo.nome }} · máximo de work-group {{ dispositivo.max_work_group_size }}</span>
              } @else if (carregandoCapacidades()) {
                <span class="nucleos">Detectando recursos OpenCL…</span>
              }
            </div>
            <input
              type="range"
              min="1"
              [max]="dispositivoSelecionado()?.max_work_group_size ?? 1"
              [value]="workGroupSelecionado()"
              class="slider"
              [disabled]="!dispositivoSelecionado()"
              aria-label="Tamanho do work-group OpenCL"
              (input)="atualizarWorkGroup($event)"
            />
            @if (dispositivoSelecionado(); as dispositivo) {
              <div>
                <button type="button" class="df-btn df-btn-secundario" (click)="usarRecomendado()">Usar recomendado</button>
                <button type="button" class="df-btn df-btn-secundario" (click)="calibrarAutomaticamente()" [disabled]="calibrando()">
                  {{ calibrando() ? 'Calibrando…' : 'Calibrar automaticamente' }}
                </button>
                <small class="ajuda-workers">
                  Recomendado: work-group {{ dispositivo.work_group_recomendado ?? dispositivo.max_work_group_size }},
                  chunk {{ dispositivo.chunk_recomendado ?? 'automático' }}
                </small>
              </div>
            }
            <small class="ajuda-workers">
              {{ tipoBenchmarkSelecionado() === 'COMPARATIVO'
                ? 'O benchmark executará primeiro o baseline sequencial e depois a configuração paralela selecionada.'
                : 'O benchmark executará somente a configuração paralela selecionada, sem baseline sequencial.' }}
            </small>
          </div>

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
  workGroupSelecionado = signal(1);
  modoSelecionado = signal<'SEQUENCIAL' | 'PARALELO'>('SEQUENCIAL');
  tipoBenchmarkSelecionado = signal<'COMPARATIVO' | 'PARALELO_APENAS'>('COMPARATIVO');
  datasetControl = this.fb.nonNullable.control(0);
  carregando = signal(false);
  calibrando = signal(false);
  resultadoCalibracao = signal<OpenCLCalibrationResult | null>(null);
  carregandoDatasets = signal(true);
  erro = signal<string | null>(null);

  ngOnInit(): void {
    this.openClDeviceService.obterCapacidades().pipe(
      finalize(() => this.carregandoCapacidades.set(false))
    ).subscribe({
      next: (capacidades) => {
        this.capacidades.set(capacidades);
        const selected = capacidades.dispositivos.find((device) => device.tipo === 'CPU')
          ?? capacidades.dispositivos[0];
        this.tipoDispositivoSelecionado.set(selected?.tipo ?? null);
        this.workGroupSelecionado.set(
          selected?.work_group_recomendado
            ?? Math.min(4, selected?.max_work_group_size ?? 1)
        );
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

  usarRecomendado(): void {
    const device = this.dispositivoSelecionado();
    if (!device) return;
    this.workGroupSelecionado.set(Math.min(
      device.work_group_recomendado ?? 1,
      device.max_work_group_size
    ));
  }

  calibrarAutomaticamente(): void {
    const device = this.dispositivoSelecionado();
    if (!device) return;
    this.calibrando.set(true);
    this.openClDeviceService.calibrar({
      tipo_dispositivo: device.tipo,
      tempo_maximo_s: 5,
    }).pipe(finalize(() => this.calibrando.set(false))).subscribe({
      next: (resultado) => {
        this.resultadoCalibracao.set(resultado);
        this.workGroupSelecionado.set(Math.min(
          resultado.work_group_size_recomendado,
          device.max_work_group_size
        ));
      },
      error: () => this.erro.set('Não foi possível calibrar o OpenCL.'),
    });
  }

  selecionarModo(modo: 'SEQUENCIAL' | 'PARALELO'): void {
    this.modoSelecionado.set(modo);
  }

  selecionarTipoBenchmark(tipo: 'COMPARATIVO' | 'PARALELO_APENAS'): void {
    this.tipoBenchmarkSelecionado.set(tipo);
    this.modoSelecionado.set('PARALELO');
  }

  atualizarWorkGroup(event: Event): void {
    const workGroupSize = Number((event.target as HTMLInputElement).value);
    this.workGroupSelecionado.set(workGroupSize);
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
      this.workGroupSelecionado.set(Math.min(
        device.work_group_recomendado ?? this.workGroupSelecionado(),
        device.max_work_group_size
      ));
    }
  }

  executarBateria(): void {
    const idModelo = this.modelos()[0]?.id_modelo;
    if (!this.datasetControl.value || !idModelo) {
      this.erro.set('Selecione um dataset com modelo treinado disponível.');
      return;
    }

    const configuracoes: BenchmarkConfiguracao[] = [];
    if (this.tipoBenchmarkSelecionado() === 'COMPARATIVO') {
      configuracoes.push({
        modo_execucao: 'SEQUENCIAL',
        work_group_size: 1,
        rotulo: 'Sequencial (Baseline)',
      });
    }
    configuracoes.push({
      modo_execucao: 'PARALELO',
      work_group_size: this.workGroupSelecionado(),
      tipo_dispositivo: this.tipoDispositivoSelecionado(),
      rotulo: `Paralelo ${this.tipoDispositivoSelecionado()} (work-group ${this.workGroupSelecionado()})`,
    });

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
