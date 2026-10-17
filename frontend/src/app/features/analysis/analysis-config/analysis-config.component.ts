import { Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { finalize } from 'rxjs';
import { DatasetService } from '../../../core/services/dataset.service';
import { AnalysisService } from '../../../core/services/analysis.service';
import { Dataset, ModeloDeteccao } from '../../../core/models/dataset.model';
import { OpenCLCapabilities, OpenCLDevice } from '../../../core/models/opencl.model';
import { ModoExecucao } from '../../../core/models/enums';
import { OpenClDeviceService } from '../../../core/services/opencl-device.service';
import { NotificationService } from '../../../core/services/notification.service';
import { StyledSelectComponent, StyledSelectOption } from '../../../shared/components/styled-select/styled-select.component';

@Component({
  selector: 'app-analysis-config',
  standalone: true,
  imports: [ReactiveFormsModule, StyledSelectComponent],
  template: `
    <section class="df-pagina-estreita">
      <header class="page-header">
        <div class="page-header__copy">
          <p class="page-eyebrow">Análise</p>
          <h1 class="page-title">Configurar análise</h1>
        </div>
      </header>

      <div class="df-card cartao">

      @if (carregandoDatasets()) {
        <div class="carregando" role="status" aria-live="polite">
          <span class="df-spinner df-spinner-suave" aria-hidden="true"></span>
          <p>Carregando datasets…</p>
        </div>
      } @else if (erroDatasets()) {
        <div class="box-erro">
          <p>{{ erroDatasets() }}</p>
          <button class="df-btn df-btn-secundario" type="button" (click)="carregarDados()">Tentar novamente</button>
        </div>
      } @else if (!datasets().length) {
        <p class="df-vazio">Nenhum dataset disponível para análise.</p>
      } @else if (carregandoModelos()) {
        <p class="df-vazio">Datasets carregados. Consultando modelos de análise…</p>
      } @else if (erroModelos() || !modelos().length) {
        <div class="box-aviso" role="status">
          <p>{{ erroModelos() || 'A API ainda não disponibiliza modelos para análise.' }}</p>
          <p>{{ datasets().length }} dataset(s) carregado(s). A configuração será liberada quando a API de modelos estiver disponível.</p>
          <button class="df-btn df-btn-secundario" type="button" (click)="carregarModelos()">Tentar novamente</button>
        </div>
      } @else {
      <form [formGroup]="form" (ngSubmit)="executar()">
        <div class="linha-campos">
          <div>
            <label class="df-label">Dataset</label>
            <app-styled-select formControlName="id_dataset" ariaLabel="Dataset" [opcoes]="opcoesDataset" />
          </div>
          <div>
            <label class="df-label">Modelo</label>
            <app-styled-select formControlName="id_modelo" ariaLabel="Modelo" [opcoes]="opcoesModelo" />
          </div>
        </div>

        <hr class="separador" />

        <label class="df-label">Modo de execução</label>
        <div class="opcoes-modo">
          <label class="opcao">
            <input type="radio" formControlName="modo_execucao" [value]="Modo.SEQUENCIAL" />
            Sequencial (baseline)
          </label>
          <label class="opcao">
            <input type="radio" formControlName="modo_execucao" [value]="Modo.PARALELO" />
            Paralelo
          </label>
        </div>

        @if (form.controls.modo_execucao.value === Modo.PARALELO) {
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
                <span>Workers por grupo: {{ form.controls.num_workers.value }}</span>
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
                formControlName="num_workers"
                class="slider"
                [disabled]="!dispositivoSelecionado()"
              />
              @if (!carregandoCapacidades() && !capacidades()) {
                <small class="ajuda-workers">Não foi possível detectar dispositivos OpenCL. Tente atualizar a página ou verifique o runtime OpenCL do backend.</small>
              }
          </div>
        }

        <details class="avancado">
          <summary>Configurações avançadas</summary>
          <div class="linha-campos campos-avancados">
            <div>
              <label class="df-label">Tamanho do bloco</label>
              <input class="df-input" type="number" min="1" step="1" formControlName="tamanho_chunk" placeholder="Automático" />
              @if (form.controls.tamanho_chunk.invalid && form.controls.tamanho_chunk.touched) {
                <small class="validacao-erro">Informe um tamanho de bloco inteiro maior que zero ou deixe o campo vazio para usar o padrão.</small>
              }
            </div>
            <div>
              <label class="df-label">Limiar de decisão</label>
              <input class="df-input" type="number" step="0.01" min="0" max="1" formControlName="limiar_decisao" />
            </div>
          </div>
        </details>

        @if (erro()) {
          <div class="df-alerta df-alerta-erro" style="margin-top:16px" role="alert">
            <span>{{ erro() }}</span>
            <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="erro.set(null)">×</button>
          </div>
        }

        <div class="acoes">
          <button type="button" class="df-btn df-btn-secundario" (click)="cancelar()">Cancelar</button>
          <button class="df-btn df-btn-primary" type="submit" [disabled]="form.invalid || carregando() || (form.controls.modo_execucao.value === Modo.PARALELO && !dispositivoSelecionado())">
            {{ carregando() ? 'Enviando…' : 'Executar análise' }}
          </button>
        </div>
      </form>
      }
      </div>
    </section>
  `,
  styles: [
    `
      .cartao { width: 100%; }
      .carregando { display: flex; align-items: center; gap: 10px; padding: 24px 4px; color: var(--cor-texto-suave); font-size: 13px; }
      .box-erro {
        display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px; border-radius: 10px;
        background: var(--cor-erro-bg); border: 1px solid var(--cor-erro-texto); color: var(--cor-erro-texto);
      }
      .box-aviso { display: grid; gap: 12px; padding: 16px; border-radius: 8px; background: var(--cor-aviso-bg); color: var(--cor-aviso-texto); }
      .box-aviso .df-btn { justify-self: start; }
      .linha-campos { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
      .separador { border: none; border-top: 1px solid var(--cor-borda); margin: 24px 0; }
      .opcoes-modo { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }
      .opcao { display: flex; align-items: center; gap: 8px; font-size: 14px; }
      .caixa-workers { background: var(--cor-superficie-suave); color: var(--cor-texto); border: 1px solid var(--cor-borda); border-radius: 8px; padding: 14px 16px; margin-top: 16px; }
      .linha-slider { display: flex; justify-content: space-between; font-size: 13.5px; margin-bottom: 8px; }
      .nucleos { color: var(--cor-texto-suave); }
      .seletor-dispositivo { display: grid; gap: 7px; margin-bottom: 14px; color: var(--cor-texto); font-size: 13px; font-weight: 600; }
      .seletor-dispositivo select { width: 100%; padding: 9px 11px; border: 1px solid var(--cor-borda); border-radius: 7px; background: var(--cor-superficie); color: var(--cor-texto); font: inherit; }
      .slider { width: 100%; accent-color: var(--cor-primaria); }
      .ajuda-workers { display: block; margin-top: 7px; color: var(--cor-texto-suave); font-size: 11px; }
      .avancado { margin-top: 20px; border-top: 1px solid var(--cor-borda); padding-top: 16px; }
      .avancado summary { cursor: pointer; color: var(--cor-texto-suave); font-size: 13px; font-weight: 600; }
      .campos-avancados { margin-top: 16px; }
      .acoes { display: flex; justify-content: flex-end; gap: 10px; margin-top: 28px; }
    `,
  ],
})
export class AnalysisConfigComponent implements OnInit {
  private fb = inject(FormBuilder);
  private datasetService = inject(DatasetService);
  private analysisService = inject(AnalysisService);
  private openClDeviceService = inject(OpenClDeviceService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  Modo = ModoExecucao;
  datasets = signal<Dataset[]>([]);
  modelos = signal<ModeloDeteccao[]>([]);
  opcoesDataset: StyledSelectOption[] = [];
  opcoesModelo: StyledSelectOption[] = [];
  capacidades = signal<OpenCLCapabilities | null>(null);
  tipoDispositivoSelecionado = signal<'CPU' | 'GPU' | null>(null);
  carregandoCapacidades = signal(true);
  carregando = signal(false);
  carregandoDatasets = signal(true);
  carregandoModelos = signal(true);
  erro = signal<string | null>(null);
  erroDatasets = signal<string | null>(null);
  erroModelos = signal<string | null>(null);
  private notificationService = inject(NotificationService);

  form = this.fb.nonNullable.group({
    id_dataset: [0, Validators.required],
    id_modelo: [0, Validators.required],
    modo_execucao: [ModoExecucao.SEQUENCIAL, Validators.required],
    num_workers: [1],
    tamanho_chunk: [null as number | null, Validators.min(1)],
    limiar_decisao: [0.5, [Validators.min(0), Validators.max(1)]],
  });

  ngOnInit(): void {
    this.carregarDados();
    this.openClDeviceService.obterCapacidades().pipe(
      finalize(() => this.carregandoCapacidades.set(false))
    ).subscribe({
      next: (capacidades) => {
        this.capacidades.set(capacidades);
        const selected = capacidades.dispositivos.find((device) => device.tipo === 'GPU')
          ?? capacidades.dispositivos[0];
        this.tipoDispositivoSelecionado.set(selected?.tipo ?? null);
        this.form.controls.num_workers.setValue(Math.min(4, selected?.max_workers ?? 1));
      },
      error: (error: unknown) => {
        const message =
          error instanceof HttpErrorResponse && typeof error.error?.detail === 'string'
            ? error.error.detail
            : 'Não foi possível detectar os dispositivos OpenCL do backend.';
        this.erro.set(message);
      },
    });
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
      this.form.controls.num_workers.setValue(
        Math.min(this.form.controls.num_workers.value, device.max_workers)
      );
    }
  }

  carregarDados(): void {
    this.carregarDatasets();
    this.carregarModelos();
  }

  carregarDatasets(): void {
    this.carregandoDatasets.set(true);
    this.erroDatasets.set(null);
    this.datasetService
      .listar()
      .pipe(finalize(() => this.carregandoDatasets.set(false)))
      .subscribe({
        next: (datasets) => {
        this.datasets.set(datasets);
        this.opcoesDataset = datasets.map((ds) => ({ valor: String(ds.id_dataset), rotulo: ds.nome }));
        const datasetIdParam = Number(this.route.snapshot.queryParamMap.get('datasetId'));
        const datasetSelecionado = datasets.find((d) => d.id_dataset === datasetIdParam) ?? datasets[0];
        if (datasetSelecionado) this.form.controls.id_dataset.setValue(datasetSelecionado.id_dataset);
      },
      error: (error: unknown) => this.erroDatasets.set(this.mensagemErro(error, 'datasets')),
    });
  }

  carregarModelos(): void {
    this.carregandoModelos.set(true);
    this.erroModelos.set(null);
    this.datasetService
      .listarModelos()
      .pipe(finalize(() => this.carregandoModelos.set(false)))
      .subscribe({
        next: (modelos) => {
          this.modelos.set(modelos);
          this.opcoesModelo = modelos.map((modelo) => ({ valor: String(modelo.id_modelo), rotulo: `${modelo.nome} ${modelo.versao}` }));
          if (modelos[0]) this.form.controls.id_modelo.setValue(modelos[0].id_modelo);
        },
        error: (error: unknown) => this.erroModelos.set(this.mensagemErro(error, 'modelos')),
      });
  }

  private mensagemErro(error: unknown, recurso: 'datasets' | 'modelos'): string {
    if (error instanceof HttpErrorResponse && error.status === 404 && recurso === 'modelos') {
      return 'A API de modelos ainda não está disponível. Os datasets foram carregados, mas não é possível configurar a análise.';
    }
    if (error instanceof HttpErrorResponse && error.status === 0) {
      return 'Não foi possível conectar à API. Verifique se o backend está em execução.';
    }
    if (error instanceof HttpErrorResponse && typeof error.error?.detail === 'string') {
      return error.error.detail;
    }
    return `Não foi possível carregar ${recurso}.`;
  }

  cancelar(): void {
    this.router.navigateByUrl('/datasets');
  }

  executar(): void {
    if (this.form.invalid) return;
    this.carregando.set(true);
    this.erro.set(null);

    const valores = this.form.getRawValue();
    this.analysisService
      .executar({
        id_dataset: valores.id_dataset,
        id_modelo: valores.id_modelo,
        modo_execucao: valores.modo_execucao,
        num_workers: valores.modo_execucao === ModoExecucao.SEQUENCIAL ? 1 : valores.num_workers,
        tipo_dispositivo:
          valores.modo_execucao === ModoExecucao.PARALELO
            ? this.tipoDispositivoSelecionado() ?? undefined
            : undefined,
        tamanho_chunk: valores.tamanho_chunk ?? undefined,
        limiar_decisao: valores.limiar_decisao,
      })
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (execucao) => {
          this.notificationService.showSuccess('Análise iniciada com sucesso.');
          this.router.navigate(['/analises', execucao.id_execucao, 'execucao']);
        },
        error: (error: unknown) => {
          const message =
            error instanceof HttpErrorResponse &&
            typeof error.error?.detail === 'string'
              ? error.error.detail
              : 'Não foi possível iniciar a análise.';
          this.erro.set(message);
          this.notificationService.showError(message);
        },
      });
  }
}
