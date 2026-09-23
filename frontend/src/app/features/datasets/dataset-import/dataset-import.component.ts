import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { DatasetService } from '../../../core/services/dataset.service';
import { StyledSelectComponent, StyledSelectOption } from '../../../shared/components/styled-select/styled-select.component';

@Component({
  selector: 'app-dataset-import',
  standalone: true,
  imports: [ReactiveFormsModule, RouterLink, StyledSelectComponent],
  template: `
    <div class="cabecalho">
      <a routerLink="/datasets" class="voltar">← Voltar</a>
      <h1>Importar conjunto de transações</h1>
    </div>

    <div class="df-card">
      <div
        class="dropzone"
        [class.sobre]="arrastando()"
        (dragover)="onDragOver($event)"
        (dragleave)="arrastando.set(false)"
        (drop)="onDrop($event)"
        (click)="inputArquivo.click()"
      >
        @if (arquivo(); as f) {
          <p>{{ f.name }} ({{ (f.size / 1024 / 1024).toFixed(2) }} MB)</p>
        } @else {
          <p>Arraste o arquivo .csv ou clique aqui</p>
        }
      </div>
      <input #inputArquivo type="file" accept=".csv" hidden (change)="onSelecionarArquivo($event)" />

      <form [formGroup]="form" (ngSubmit)="importar()">
        <div class="linha-campos">
          <div>
            <label class="df-label">Nome</label>
            <input class="df-input" formControlName="nome" placeholder="Credit Card ULB" />
          </div>
          <div>
            <label class="df-label">Origem</label>
            <app-styled-select formControlName="origem" [opcoes]="opcoesOrigem" />
          </div>
        </div>

        @if (erro()) {
          <p class="df-erro-msg" style="margin-top:16px">{{ erro() }}</p>
        }

        <div class="acoes">
          <a routerLink="/datasets" class="df-btn df-btn-secundario">Cancelar</a>
          <button
            class="df-btn df-btn-primary"
            type="submit"
            [disabled]="form.invalid || !arquivo() || carregando()"
          >
            {{ carregando() ? 'Importando…' : 'Importar Dataset' }}
          </button>
        </div>
      </form>
    </div>
  `,
  styles: [
    `
      .cabecalho { margin-bottom: 24px; }
      .voltar { font-size: 13.5px; color: var(--cor-texto-suave); display: inline-block; margin-bottom: 8px; }
      .cabecalho h1 { font-size: 24px; font-weight: 700; }
      .dropzone {
        border: 2px dashed var(--cor-borda);
        border-radius: 10px;
        padding: 48px 16px;
        text-align: center;
        color: var(--cor-texto-suave);
        cursor: pointer;
        margin-bottom: 24px;
        transition: border-color 0.15s ease, background 0.15s ease;
      }
      .dropzone.sobre { border-color: var(--cor-primaria); background: #eff6ff; }
      .linha-campos { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; }
      .acoes { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
    `,
  ],
})
export class DatasetImportComponent {
  opcoesOrigem: StyledSelectOption[] = [
    { valor: 'Pública', rotulo: 'Pública' },
    { valor: 'Sintética', rotulo: 'Sintética' },
    { valor: 'Privada', rotulo: 'Privada' },
  ];
  private fb = inject(FormBuilder);
  private datasetService = inject(DatasetService);
  private router = inject(Router);

  arquivo = signal<File | null>(null);
  arrastando = signal(false);
  carregando = signal(false);
  erro = signal<string | null>(null);

  form = this.fb.nonNullable.group({
    nome: ['', Validators.required],
    origem: ['Pública', Validators.required],
    descricao: [''],
  });

  onDragOver(evento: DragEvent): void {
    evento.preventDefault();
    this.arrastando.set(true);
  }

  onDrop(evento: DragEvent): void {
    evento.preventDefault();
    this.arrastando.set(false);
    const arquivo = evento.dataTransfer?.files?.[0];
    if (arquivo) this.definirArquivo(arquivo);
  }

  onSelecionarArquivo(evento: Event): void {
    const arquivo = (evento.target as HTMLInputElement).files?.[0];
    if (arquivo) this.definirArquivo(arquivo);
  }

  private definirArquivo(arquivo: File): void {
    this.arquivo.set(arquivo);
    if (!this.form.controls.nome.value) {
      this.form.controls.nome.setValue(arquivo.name.replace(/\.csv$/i, ''));
    }
  }

  importar(): void {
    const arquivo = this.arquivo();
    if (this.form.invalid || !arquivo) return;

    this.carregando.set(true);
    this.erro.set(null);
    const { nome, origem, descricao } = this.form.getRawValue();

    this.datasetService
      .importar({ nome, origem, descricao, arquivo })
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (ds) => this.router.navigate(['/analises/nova'], { queryParams: { datasetId: ds.id_dataset } }),
        error: () => this.erro.set('Não foi possível importar o dataset. Verifique o formato do arquivo.'),
      });
  }
}
