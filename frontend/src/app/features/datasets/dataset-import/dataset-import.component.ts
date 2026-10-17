import { Component, DestroyRef, ElementRef, ViewChild, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ProcessManagerService } from '../../../core/services/process-manager.service';

const MAX_FILE_SIZE = 200 * 1024 * 1024;

@Component({
  selector: 'app-dataset-import',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink],
  template: `
    <section class="import-page" aria-labelledby="page-title">
      <header class="page-header">
        <div>
          <a routerLink="/datasets" class="page-backlink">← Datasets</a>
          <p class="page-eyebrow">Biblioteca de dados</p>
          <h1 id="page-title" class="page-title">Importar dataset</h1>
          <p class="page-subtitle">Adicione um CSV de transações para disponibilizá-lo na plataforma.</p>
        </div>
      </header>

      <form [formGroup]="form" (ngSubmit)="importar()" novalidate>
        <div
          class="dropzone"
          [class.sobre]="arrastando()"
          [class.com-arquivo]="arquivo()"
          (dragover)="onDragOver($event)"
          (dragleave)="onDragLeave($event)"
          (drop)="onDrop($event)"
        >
          <input
            #fileInput
            id="dataset-file"
            class="input-arquivo"
            type="file"
            accept=".csv,text/csv"
            [disabled]="carregando()"
            (change)="onSelecionarArquivo($event)"
          />
          @if (arquivo(); as file) {
            <div class="arquivo-selecionado">
              <div class="arquivo-icone" aria-hidden="true">CSV</div>
              <div class="arquivo-info">
                <strong>{{ file.name }}</strong>
                <span>{{ formatarTamanho(file.size) }}</span>
              </div>
                <label for="dataset-file" class="trocar-arquivo" [class.desabilitado]="carregando()">Trocar arquivo</label>
                <button type="button" class="remover-arquivo" [disabled]="carregando()" (click)="limparArquivo()" aria-label="Remover arquivo selecionado">×</button>
            </div>
          } @else if (carregando()) {
            <div class="arquivo-selecionado">
                <div class="arquivo-icone" aria-hidden="true">CSV</div>
                <div class="arquivo-info">
                  <strong>{{ processo()?.filename }}</strong>
                  <span>{{ formatarTamanho(processo()?.size ?? 0) }} · importação gerenciada em segundo plano</span>
                </div>
            </div>
          } @else {
            <label for="dataset-file" class="dropzone-label">
              <span class="upload-icone" aria-hidden="true">↑</span>
              <strong>Solte o CSV aqui ou <span>escolha um arquivo</span></strong>
              <small>Formato CSV · até 200 MB</small>
            </label>
          }

        </div>

        @if (carregando()) {
          <section class="progresso-importacao" aria-labelledby="progress-title" aria-live="polite">
            <div class="progresso-cabecalho">
              <div>
                <p class="progresso-etapa">{{ faseImportacao() === 'enviando' ? 'Etapa 1 de 2' : 'Etapa 2 de 2' }}</p>
                <h2 id="progress-title">{{ faseImportacao() === 'enviando' ? 'Enviando arquivo' : 'Processando dataset' }}</h2>
              </div>
              <span class="spinner progresso-spinner" aria-hidden="true"></span>
            </div>

            @if (faseImportacao() === 'enviando') {
              @if (progressoUpload() !== null) {
                <div
                  class="barra-progresso"
                  role="progressbar"
                  [attr.aria-valuenow]="progressoUpload()"
                  aria-valuemin="0"
                  aria-valuemax="100"
                  aria-label="Progresso do envio do arquivo"
                >
                  <div class="barra-preenchida" [style.width.%]="progressoUpload()"></div>
                </div>
                <div class="progresso-resumo">
                  <strong>{{ progressoUpload() }}%</strong>
                  <span>{{ formatarTamanho(bytesEnviados()) }} enviados</span>
                </div>
              } @else {
                <div class="barra-progresso indeterminada" role="progressbar" aria-label="Iniciando envio do arquivo">
                  <div class="barra-preenchida"></div>
                </div>
                <p class="texto-progresso">Preparando o envio do arquivo…</p>
              }
              <p class="texto-progresso">O tempo restante é uma estimativa e pode variar conforme sua conexão.</p>
            } @else {
              <div class="barra-progresso concluida" role="progressbar" aria-valuenow="100" aria-valuemin="0" aria-valuemax="100" aria-label="Envio do arquivo concluído">
                <div class="barra-preenchida" style="width: 100%"></div>
              </div>
              <p class="texto-progresso"><strong>Arquivo enviado.</strong> O servidor está validando o CSV, verificando duplicidade e gravando as transações. Essa etapa não tem percentual disponível.</p>
            }

            <div class="detalhes-progresso">
              <div><span>Arquivo</span><strong>{{ processo()?.filename ?? arquivo()?.name }}</strong></div>
              <div><span>Tamanho</span><strong>{{ formatarTamanho(processo()?.size ?? arquivo()?.size ?? 0) }}</strong></div>
              <div><span>Tempo decorrido</span><strong>{{ formatarDuracao(tempoDecorrido()) }}</strong></div>
              @if (faseImportacao() === 'enviando') {
                <div><span>Velocidade média</span><strong>{{ velocidadeMedia() > 0 ? formatarTamanho(velocidadeMedia()) + '/s' : 'Calculando…' }}</strong></div>
                <div><span>Tempo estimado para envio</span><strong>{{ estimativaEnvio() }}</strong></div>
              }
            </div>

            <ol class="etapas-importacao">
              <li [class.concluida]="faseImportacao() === 'processando'">
                <span class="etapa-icone">{{ faseImportacao() === 'processando' ? '✓' : '1' }}</span>
                <span>Transferência do arquivo</span>
                <strong>{{ faseImportacao() === 'processando' ? 'Concluída' : 'Em andamento' }}</strong>
              </li>
              <li [class.ativa]="faseImportacao() === 'processando'">
                <span class="etapa-icone">2</span>
                <span>Validação e importação pelo servidor</span>
                <strong>{{ faseImportacao() === 'processando' ? 'Em andamento' : 'Aguardando' }}</strong>
              </li>
            </ol>
          </section>
        }
        @if (processo()?.status === 'completed') {
          <div class="importacao-concluida" role="status">
            <div>
              <strong>Importação concluída</strong>
              <p>{{ processo()?.filename }} foi adicionado como dataset.</p>
            </div>
            <div class="acoes-concluida">
              <a
                class="df-btn df-btn-primary"
                [routerLink]="['/analises/nova']"
                [queryParams]="{ datasetId: processo()?.dataset?.id_dataset }"
              >Configurar análise</a>
              <button type="button" class="fechar-concluida" (click)="processManager.dismissDatasetImport()">Dispensar</button>
            </div>
          </div>
        }

        <div class="form-section">
          <h2>Identificação</h2>
          <div class="campos">
            <div class="campo">
              <label for="dataset-name">Nome do dataset <span aria-hidden="true">*</span></label>
              <input id="dataset-name" class="df-input" formControlName="nome" maxlength="160" placeholder="Ex.: Transações setembro" />
              @if (form.controls.nome.touched && form.controls.nome.invalid) {
                <small class="ajuda erro-campo">Informe um nome para identificar este dataset.</small>
              }
            </div>
            <div class="campo">
              <label for="dataset-origin">Origem <span aria-hidden="true">*</span></label>
              <select id="dataset-origin" class="df-select" formControlName="origem">
                <option value="Pública">Pública</option>
                <option value="Sintética">Sintética</option>
                <option value="Privada">Privada</option>
              </select>
            </div>
            <div class="campo campo-largo">
              <label for="dataset-description">Descrição <span class="opcional">Opcional</span></label>
              <textarea id="dataset-description" class="df-input descricao" formControlName="descricao" rows="3" maxlength="1000" placeholder="Contexto ou observações sobre o conjunto de dados"></textarea>
            </div>
          </div>
        </div>

        @if (erro()) {
          <div class="alerta erro" role="alert" aria-live="assertive">
            <span>{{ erro() }}</span>
            <button type="button" aria-label="Fechar erro" (click)="limparErro()">×</button>
          </div>
        }

        <footer class="acoes">
          <a routerLink="/datasets" class="df-btn df-btn-secundario">Cancelar</a>
          <button class="df-btn df-btn-primary" type="submit" [disabled]="!podeEnviar()">
            @if (carregando()) {
              <span class="spinner" aria-hidden="true"></span> Importando…
            } @else {
              Importar dataset
            }
          </button>
        </footer>
      </form>
    </section>
  `,
  styles: [`
    :host { display: block; }
    .import-page { max-width: 920px; margin: 0 auto; }
    .dropzone { position: relative; min-height: 174px; display: grid; place-items: center; margin-bottom: 22px; border: 1px dashed var(--cor-borda); border-radius: 7px; background: var(--cor-superficie); transition: background .15s ease, border-color .15s ease; }
    .dropzone.sobre, .dropzone:focus-within { border-color: var(--cor-primaria); background: var(--cor-superficie-suave); }
    .dropzone.com-arquivo { min-height: 100px; padding: 12px 18px; }
    .input-arquivo { position: absolute; width: 1px; height: 1px; opacity: 0; overflow: hidden; }
    .dropzone-label { width: 100%; min-height: 172px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 9px; cursor: pointer; text-align: center; }
    .upload-icone { display: grid; place-items: center; width: 35px; height: 35px; border: 1px solid var(--cor-borda); border-radius: 50%; color: var(--cor-primaria); font-size: 20px; }
    .dropzone-label strong { color: var(--cor-texto); font-size: 14px; }
    .dropzone-label strong span { color: var(--cor-primaria); }
    .dropzone-label small { color: var(--cor-texto-suave); font-size: 12px; }
    .arquivo-selecionado { width: 100%; display: flex; align-items: center; gap: 12px; }
    .arquivo-icone { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 6px; background: var(--cor-superficie-suave); color: var(--cor-primaria); font-size: 10px; font-weight: 700; }
    .arquivo-info { display: grid; gap: 4px; min-width: 0; flex: 1; }
    .arquivo-info strong { overflow: hidden; color: var(--cor-texto); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
    .arquivo-info span { color: var(--cor-texto-suave); font-size: 12px; }
    .trocar-arquivo { color: var(--cor-primaria); font-size: 12px; font-weight: 600; cursor: pointer; white-space: nowrap; }
    .trocar-arquivo:hover { text-decoration: underline; }
    .remover-arquivo { width: 32px; height: 32px; border: 0; border-radius: 5px; background: transparent; color: var(--cor-texto-suave); font-size: 20px; cursor: pointer; }
    .remover-arquivo:hover { background: var(--cor-erro-bg); color: var(--cor-erro-texto); }
    .form-section { padding: 20px 0 24px; border-top: 1px solid var(--cor-borda); }
    .form-section h2 { margin: 0 0 18px; font-size: 15px; }
    .campos { display: grid; grid-template-columns: 1fr 1fr; gap: 18px 20px; }
    .campo { min-width: 0; }
    .campo label { display: block; margin-bottom: 7px; color: var(--cor-texto); font-size: 12px; font-weight: 600; }
    .campo label > span:not(.opcional) { color: var(--cor-erro-texto); }
    .opcional { margin-left: 5px; color: var(--cor-texto-suave); font-weight: 400; }
    .campo-largo { grid-column: 1 / -1; }
    .descricao { display: block; resize: vertical; font: inherit; }
    .ajuda { display: block; margin-top: 5px; font-size: 11px; }
    .erro-campo { color: var(--cor-erro-texto); }
    .alerta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin: 0 0 18px; padding: 11px 13px; border-radius: 6px; font-size: 13px; }
    .alerta.erro { background: var(--cor-erro-bg); color: var(--cor-erro-texto); }
    .alerta button { border: 0; background: transparent; color: inherit; font-size: 18px; cursor: pointer; }
    .progresso-importacao { display: grid; gap: 14px; margin: 4px 0 22px; padding: 18px; border: 1px solid var(--cor-borda); border-radius: 10px; background: var(--cor-superficie); color: var(--cor-texto); box-shadow: 0 4px 16px rgba(15, 23, 42, .06); }
    .importacao-concluida { display: flex; justify-content: space-between; align-items: center; gap: 16px; margin: 4px 0 22px; padding: 16px; border: 1px solid var(--cor-sucesso-texto); border-radius: 9px; background: var(--cor-sucesso-bg); color: var(--cor-sucesso-texto); }
    .importacao-concluida p { margin-top: 4px; font-size: 12px; }
    .acoes-concluida { display: flex; align-items: center; gap: 10px; }
    .fechar-concluida { border: 1px solid currentColor; border-radius: 6px; padding: 8px 10px; background: transparent; color: inherit; font: inherit; font-size: 12px; cursor: pointer; }
    .progresso-cabecalho { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
    .progresso-etapa { margin-bottom: 4px; color: var(--cor-primaria); font-size: 11px; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; }
    .progresso-cabecalho h2 { margin: 0; font-size: 15px; }
    .progresso-spinner { border-color: var(--cor-borda); border-top-color: var(--cor-primaria); }
    .barra-progresso { height: 9px; overflow: hidden; border-radius: 999px; background: var(--cor-superficie-suave); }
    .barra-preenchida { height: 100%; border-radius: inherit; background: linear-gradient(90deg, var(--cor-primaria), #60a5fa); transition: width .25s ease; }
    .barra-progresso.concluida .barra-preenchida { background: var(--cor-sucesso-texto); }
    .barra-progresso.indeterminada .barra-preenchida { width: 35%; animation: mover 1.3s ease-in-out infinite alternate; }
    .progresso-resumo { display: flex; justify-content: space-between; align-items: baseline; margin-top: -8px; }
    .progresso-resumo strong { color: var(--cor-primaria); font-size: 20px; }
    .progresso-resumo span, .texto-progresso { color: var(--cor-texto-suave); font-size: 12px; }
    .texto-progresso { margin: 0; line-height: 1.55; }
    .detalhes-progresso { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 10px 16px; padding: 12px 0; border-top: 1px solid var(--cor-borda); border-bottom: 1px solid var(--cor-borda); }
    .detalhes-progresso div { display: grid; gap: 4px; min-width: 0; }
    .detalhes-progresso span { color: var(--cor-texto-suave); font-size: 11px; }
    .detalhes-progresso strong { overflow: hidden; font-size: 12px; text-overflow: ellipsis; white-space: nowrap; }
    .etapas-importacao { display: grid; gap: 9px; margin: 0; padding: 0; list-style: none; }
    .etapas-importacao li { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; align-items: center; gap: 9px; color: var(--cor-texto-suave); font-size: 12px; }
    .etapas-importacao li strong { font-size: 11px; font-weight: 600; }
    .etapas-importacao li.concluida { color: var(--cor-sucesso-texto); }
    .etapas-importacao li.ativa { color: var(--cor-primaria); }
    .etapa-icone { display: grid; place-items: center; width: 22px; height: 22px; border: 1px solid var(--cor-borda); border-radius: 50%; font-size: 10px; font-weight: 700; }
    .etapas-importacao li.concluida .etapa-icone { border-color: var(--cor-sucesso-texto); background: var(--cor-sucesso-bg); }
    .etapas-importacao li.ativa .etapa-icone { border-color: var(--cor-primaria); }
    .trocar-arquivo.desabilitado { opacity: .5; pointer-events: none; }
    .remover-arquivo:disabled { opacity: .4; cursor: not-allowed; }
    @keyframes mover { from { transform: translateX(-20%); } to { transform: translateX(190%); } }
    .acoes { display: flex; justify-content: flex-end; gap: 9px; padding-top: 16px; border-top: 1px solid var(--cor-borda); }
    .df-btn-primary:disabled { opacity: .55; cursor: not-allowed; }
    .spinner { display: inline-block; width: 13px; height: 13px; border: 2px solid rgba(255,255,255,.5); border-top-color: white; border-radius: 50%; animation: girar .7s linear infinite; }
    @keyframes girar { to { transform: rotate(360deg); } }
    @media (max-width: 640px) { .campos { grid-template-columns: 1fr; } .campo-largo { grid-column: auto; } }
  `],
})
export class DatasetImportComponent {
  @ViewChild('fileInput') private fileInput?: ElementRef<HTMLInputElement>;
  private destroyRef = inject(DestroyRef);
  private fb = inject(FormBuilder);
  private router = inject(Router);
  processManager = inject(ProcessManagerService);

  arquivo = signal<File | null>(null);
  arrastando = signal(false);
  private erroLocal = signal<string | null>(null);
  processo = this.processManager.datasetImport;
  carregando = computed(() => {
    const status = this.processo()?.status;
    return (
      status === 'starting' ||
      status === 'uploading' ||
      status === 'processing' ||
      status === 'cancelling'
    );
  });
  erro = computed(() => this.erroLocal() ?? this.processo()?.error ?? null);
  faseImportacao = computed(() =>
    this.processo()?.status === 'processing' ? 'processando' : 'enviando'
  );
  progressoUpload = computed(() => this.processo()?.progress ?? null);
  bytesEnviados = computed(() => this.processo()?.bytesSent ?? 0);
  velocidadeMedia = computed(() => this.processo()?.bytesPerSecond ?? 0);
  tempoDecorrido = computed(() => this.processo()?.elapsedSeconds ?? 0);

  form = this.fb.nonNullable.group({
    nome: ['', [Validators.required, Validators.maxLength(160)]],
    origem: ['Pública', Validators.required],
    descricao: ['', Validators.maxLength(1000)],
  });

  constructor() {
    this.processManager.datasetImportCompleted
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((dataset) => {
        if (this.router.url.startsWith('/datasets/importar')) {
          this.router.navigate(['/analises/nova'], {
            queryParams: { datasetId: dataset.id_dataset },
          });
        }
      });
  }

  podeEnviar(): boolean {
    const file = this.arquivo();
    return this.form.valid && !!file && file.size <= MAX_FILE_SIZE && file.name.toLowerCase().endsWith('.csv') && !this.carregando();
  }

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.arrastando.set(true);
  }

  onDragLeave(event: DragEvent): void {
    const current = event.currentTarget as HTMLElement;
    if (!current.contains(event.relatedTarget as Node | null)) this.arrastando.set(false);
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.arrastando.set(false);
    if (this.carregando()) return;
    const file = event.dataTransfer?.files?.[0];
    if (file) this.selecionarArquivo(file);
  }

  onSelecionarArquivo(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (file) this.selecionarArquivo(file);
  }

  limparArquivo(): void {
    this.arquivo.set(null);
    if (this.fileInput) this.fileInput.nativeElement.value = '';
    this.erroLocal.set(null);
  }

  limparErro(): void {
    this.erroLocal.set(null);
    if (this.processo()?.status === 'failed') {
      this.processManager.dismissDatasetImport();
    }
  }

  formatarTamanho(bytes: number): string {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  formatarDuracao(seconds: number): string {
    const minutes = Math.floor(seconds / 60);
    const remaining = seconds % 60;
    return minutes ? `${minutes} min ${remaining} s` : `${remaining} s`;
  }

  estimativaEnvio(): string {
    const speed = this.velocidadeMedia();
    const remaining = (this.processo()?.size ?? this.arquivo()?.size ?? 0) - this.bytesEnviados();
    if (speed <= 0 || remaining <= 0) return 'Calculando…';
    return `~${this.formatarDuracao(Math.ceil(remaining / speed))}`;
  }

  importar(): void {
    const file = this.arquivo();
    if (!this.podeEnviar() || !file) return;
    this.erroLocal.set(null);
    const { nome, origem, descricao } = this.form.getRawValue();
    if (!this.processManager.startDatasetImport({ nome, origem, descricao, arquivo: file })) {
      this.erroLocal.set('Já existe uma importação de dataset em andamento.');
    }
  }

  private selecionarArquivo(file: File): void {
    if (this.carregando()) return;
    this.erroLocal.set(null);
    if (!file.name.toLowerCase().endsWith('.csv')) {
      this.arquivo.set(null);
      this.erroLocal.set('Selecione um arquivo com extensão .csv.');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      this.arquivo.set(null);
      this.erroLocal.set('O arquivo excede o limite de 200 MB.');
      return;
    }
    this.arquivo.set(file);
    if (!this.form.controls.nome.value) this.form.controls.nome.setValue(file.name.replace(/\.csv$/i, ''));
  }

}
