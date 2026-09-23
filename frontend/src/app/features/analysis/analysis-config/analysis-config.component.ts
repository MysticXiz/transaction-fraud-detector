import { Component, OnInit, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { finalize, forkJoin } from 'rxjs';
import { DatasetService } from '../../../core/services/dataset.service';
import { AnalysisService } from '../../../core/services/analysis.service';
import { Dataset, ModeloDeteccao } from '../../../core/models/dataset.model';
import { ModoExecucao } from '../../../core/models/enums';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-analysis-config',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="df-card cartao">
      <h1 class="titulo">Configurar análise</h1>

      @if (carregandoDados()) {
        <p class="df-vazio">Carregando datasets e modelos…</p>
      } @else if (erroDados()) {
        <div class="box-erro">
          <p>{{ erroDados() }}</p>
          <button class="df-btn df-btn-secundario" type="button" (click)="carregarDados()">Tentar novamente</button>
        </div>
      } @else {
      <form [formGroup]="form" (ngSubmit)="executar()">
        <div class="linha-campos">
          <div>
            <label class="df-label">Dataset</label>
            <select class="df-select" formControlName="id_dataset">
              @for (ds of datasets(); track ds.id_dataset) {
                <option [value]="ds.id_dataset">{{ ds.nome }}</option>
              }
            </select>
          </div>
          <div>
            <label class="df-label">Modelo</label>
            <select class="df-select" formControlName="id_modelo">
              @for (m of modelos(); track m.id_modelo) {
                <option [value]="m.id_modelo">{{ m.nome }} {{ m.versao }}</option>
              }
            </select>
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
            <div class="linha-slider">
              <span>Workers: {{ form.controls.num_workers.value }}</span>
              <span class="nucleos">{{ nucleosDetectados() }} núcleos detectados</span>
            </div>
            <input
              type="range"
              min="1"
              [max]="nucleosDetectados()"
              formControlName="num_workers"
              class="slider"
            />
          </div>
        }

        <div class="linha-campos" style="margin-top:20px">
          <div>
            <label class="df-label">Tamanho do bloco</label>
            <input class="df-input" type="number" formControlName="tamanho_chunk" placeholder="ex.: 10000" />
          </div>
          <div>
            <label class="df-label">Limiar de decisão</label>
            <input class="df-input" type="number" step="0.01" min="0" max="1" formControlName="limiar_decisao" />
          </div>
        </div>

        @if (erro()) {
          <p class="df-erro-msg" style="margin-top:16px">{{ erro() }}</p>
        }

        <div class="acoes">
          <button type="button" class="df-btn df-btn-secundario" (click)="cancelar()">Cancelar</button>
          <button class="df-btn df-btn-primary" type="submit" [disabled]="form.invalid || carregando()">
            {{ carregando() ? 'Enviando…' : 'Executar análise' }}
          </button>
        </div>
      </form>
      }
    </div>
  `,
  styles: [
    `
      .cartao { max-width: 720px; }
      .titulo { font-size: 22px; font-weight: 700; margin-bottom: 22px; }
      .box-erro {
        display: flex; align-items: center; justify-content: space-between; gap: 12px; padding: 16px; border-radius: 10px;
        background: var(--cor-erro-bg); border: 1px solid var(--cor-erro-texto); color: var(--cor-erro-texto);
      }
      .linha-campos { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
      .separador { border: none; border-top: 1px solid var(--cor-borda); margin: 24px 0; }
      .opcoes-modo { display: flex; flex-direction: column; gap: 10px; margin-top: 8px; }
      .opcao { display: flex; align-items: center; gap: 8px; font-size: 14px; }
      .caixa-workers { background: #f9fafb; border-radius: 8px; padding: 14px 16px; margin-top: 16px; }
      .linha-slider { display: flex; justify-content: space-between; font-size: 13.5px; margin-bottom: 8px; }
      .nucleos { color: var(--cor-texto-suave); }
      .slider { width: 100%; }
      .acoes { display: flex; justify-content: flex-end; gap: 10px; margin-top: 28px; }
    `,
  ],
})
export class AnalysisConfigComponent implements OnInit {
  private fb = inject(FormBuilder);
  private datasetService = inject(DatasetService);
  private analysisService = inject(AnalysisService);
  private route = inject(ActivatedRoute);
  private router = inject(Router);

  Modo = ModoExecucao;
  datasets = signal<Dataset[]>([]);
  modelos = signal<ModeloDeteccao[]>([]);
  nucleosDetectados = signal<number>(navigator.hardwareConcurrency || 4);
  carregando = signal(false);
  carregandoDados = signal(true);
  erro = signal<string | null>(null);
  erroDados = signal<string | null>(null);
  private notificationService = inject(NotificationService);

  form = this.fb.nonNullable.group({
    id_dataset: [0, Validators.required],
    id_modelo: [0, Validators.required],
    modo_execucao: [ModoExecucao.PARALELO, Validators.required],
    num_workers: [Math.max(1, Math.floor((navigator.hardwareConcurrency || 4) / 2))],
    tamanho_chunk: [null as number | null],
    limiar_decisao: [0.5, [Validators.min(0), Validators.max(1)]],
  });

  ngOnInit(): void {
    this.carregarDados();
  }

  carregarDados(): void {
    this.carregandoDados.set(true);
    this.erroDados.set(null);

    forkJoin({
      datasets: this.datasetService.listar(),
      modelos: this.datasetService.listarModelos(),
    }).subscribe({
      next: ({ datasets, modelos }) => {
        this.datasets.set(datasets);
        this.modelos.set(modelos);
        const datasetIdParam = Number(this.route.snapshot.queryParamMap.get('datasetId'));
        const datasetSelecionado = datasets.find((d) => d.id_dataset === datasetIdParam) ?? datasets[0];
        if (datasetSelecionado) this.form.controls.id_dataset.setValue(datasetSelecionado.id_dataset);
        if (modelos[0]) this.form.controls.id_modelo.setValue(modelos[0].id_modelo);
        this.carregandoDados.set(false);
      },
      error: () => {
        this.carregandoDados.set(false);
        this.erroDados.set('Não foi possível carregar datasets/modelos.');
        this.notificationService.showError('Não foi possível carregar os dados da análise.');
      },
    });
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
        tamanho_chunk: valores.tamanho_chunk ?? undefined,
        limiar_decisao: valores.limiar_decisao,
      })
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (execucao) => {
          this.notificationService.showSuccess('Análise iniciada com sucesso.');
          this.router.navigate(['/analises', execucao.id_execucao, 'execucao']);
        },
        error: () => {
          this.erro.set('Não foi possível iniciar a análise.');
          this.notificationService.showError('Não foi possível iniciar a análise.');
        },
      });
  }
}
