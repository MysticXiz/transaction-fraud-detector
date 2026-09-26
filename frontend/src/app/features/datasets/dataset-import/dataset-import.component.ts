import { HttpErrorResponse } from '@angular/common/http';
import { Component, ElementRef, ViewChild, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { DatasetService } from '../../../core/services/dataset.service';

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
            (change)="onSelecionarArquivo($event)"
          />
          @if (arquivo(); as file) {
            <div class="arquivo-selecionado">
              <div class="arquivo-icone" aria-hidden="true">CSV</div>
              <div class="arquivo-info">
                <strong>{{ file.name }}</strong>
                <span>{{ formatarTamanho(file.size) }}</span>
              </div>
              <label for="dataset-file" class="trocar-arquivo">Trocar arquivo</label>
              <button type="button" class="remover-arquivo" (click)="limparArquivo()" aria-label="Remover arquivo selecionado">×</button>
            </div>
          } @else {
            <label for="dataset-file" class="dropzone-label">
              <span class="upload-icone" aria-hidden="true">↑</span>
              <strong>Solte o CSV aqui ou <span>escolha um arquivo</span></strong>
              <small>Formato CSV · até 200 MB</small>
            </label>
          }
        </div>

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
            <button type="button" aria-label="Fechar erro" (click)="erro.set(null)">×</button>
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
    .acoes { display: flex; justify-content: flex-end; gap: 9px; padding-top: 16px; border-top: 1px solid var(--cor-borda); }
    .df-btn-primary:disabled { opacity: .55; cursor: not-allowed; }
    .spinner { display: inline-block; width: 13px; height: 13px; border: 2px solid rgba(255,255,255,.5); border-top-color: white; border-radius: 50%; animation: girar .7s linear infinite; }
    @keyframes girar { to { transform: rotate(360deg); } }
    @media (max-width: 640px) { .campos { grid-template-columns: 1fr; } .campo-largo { grid-column: auto; } }
  `],
})
export class DatasetImportComponent {
  @ViewChild('fileInput') private fileInput?: ElementRef<HTMLInputElement>;
  private fb = inject(FormBuilder);
  private datasetService = inject(DatasetService);
  private router = inject(Router);

  arquivo = signal<File | null>(null);
  arrastando = signal(false);
  carregando = signal(false);
  erro = signal<string | null>(null);

  form = this.fb.nonNullable.group({
    nome: ['', [Validators.required, Validators.maxLength(160)]],
    origem: ['Pública', Validators.required],
    descricao: ['', Validators.maxLength(1000)],
  });

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
    this.erro.set(null);
  }

  formatarTamanho(bytes: number): string {
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  }

  importar(): void {
    const file = this.arquivo();
    if (!this.podeEnviar() || !file) return;
    this.carregando.set(true);
    this.erro.set(null);
    const { nome, origem, descricao } = this.form.getRawValue();

    this.datasetService.importar({ nome, origem, descricao, arquivo: file })
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (dataset) => this.router.navigate(['/analises/nova'], { queryParams: { datasetId: dataset.id_dataset } }),
        error: (error: unknown) => this.erro.set(this.mensagemErro(error)),
      });
  }

  private selecionarArquivo(file: File): void {
    this.erro.set(null);
    if (!file.name.toLowerCase().endsWith('.csv')) {
      this.arquivo.set(null);
      this.erro.set('Selecione um arquivo com extensão .csv.');
      return;
    }
    if (file.size > MAX_FILE_SIZE) {
      this.arquivo.set(null);
      this.erro.set('O arquivo excede o limite de 200 MB.');
      return;
    }
    this.arquivo.set(file);
    if (!this.form.controls.nome.value) this.form.controls.nome.setValue(file.name.replace(/\.csv$/i, ''));
  }

  private mensagemErro(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) return 'Ocorreu um erro inesperado ao importar o dataset.';
    if (error.status === 0) return 'Não foi possível conectar ao backend. Verifique se a API está em execução.';
    const detail: unknown = error.error?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    if (Array.isArray(detail)) return detail.map((item: unknown) => typeof item === 'object' && item !== null && 'msg' in item ? String(item.msg) : '').filter(Boolean).join(' ');
    if (error.status === 413) return 'O arquivo excede o limite máximo de upload.';
    if (error.status === 401) return 'Sua sessão expirou. Entre novamente no sistema.';
    return `Não foi possível importar o dataset (HTTP ${error.status}).`;
  }
}
