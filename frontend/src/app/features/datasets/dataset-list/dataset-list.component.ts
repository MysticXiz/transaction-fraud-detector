import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { DatePipe, DecimalPipe } from '@angular/common';
import { DatasetService } from '../../../core/services/dataset.service';
import { Dataset } from '../../../core/models/dataset.model';
import { NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-dataset-list',
  standalone: true,
  imports: [RouterLink, DatePipe, DecimalPipe],
  template: `
    <div class="cabecalho">
      <div>
        <p class="eyebrow">Dados</p>
        <h1>Datasets</h1>
      </div>
      <a routerLink="/datasets/importar" class="df-btn df-btn-primary">Importar Dataset</a>
    </div>

    @if (carregando()) {
      <div class="df-card estado"><p>Carregando datasets…</p></div>
    } @else if (erro()) {
      <div class="df-card estado erro">
        <p>{{ erro() }}</p>
        <button class="df-btn df-btn-secundario" type="button" (click)="carregar()">Tentar novamente</button>
      </div>
    } @else if (datasets().length) {
      <div class="df-card sem-padding">
        <table class="df-table">
          <thead>
            <tr>
              <th>Nome</th>
              <th>Origem</th>
              <th>Registros</th>
              <th>Data</th>
              <th style="text-align:right">Ações</th>
            </tr>
          </thead>
          <tbody>
            @for (ds of datasets(); track ds.id_dataset) {
              <tr>
                <td>{{ ds.nome }}</td>
                <td>{{ ds.origem }}</td>
                <td>{{ ds.total_registros | number: '1.0-0' : 'pt-BR' }}</td>
                <td>{{ ds.importado_em | date: 'dd/MM/yyyy' }}</td>
                <td style="text-align:right">
                  <a class="df-link" [routerLink]="['/analises/nova']" [queryParams]="{ datasetId: ds.id_dataset }">
                    Analisar
                  </a>
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    } @else {
      <div class="df-card estado">
        <p>Nenhum dataset importado ainda.</p>
      </div>
    }
  `,
  styles: [
    `
      .cabecalho { display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px; }
      .cabecalho h1 { font-size: 26px; font-weight: 700; }
      .eyebrow { color: var(--cor-primaria); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 7px; }
      .estado { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
      .erro { background: #fff7f7; border: 1px solid #fecaca; }
      .sem-padding { padding: 0; overflow: hidden; }
      .sem-padding .df-table { margin: 0; }
      .sem-padding th, .sem-padding td { padding-left: 24px; padding-right: 24px; }
    `,
  ],
})
export class DatasetListComponent implements OnInit {
  private datasetService = inject(DatasetService);
  private notificationService = inject(NotificationService);
  datasets = signal<Dataset[]>([]);
  carregando = signal(true);
  erro = signal<string | null>(null);

  ngOnInit(): void {
    this.carregar();
  }

  carregar(): void {
    this.carregando.set(true);
    this.erro.set(null);

    this.datasetService.listar().subscribe({
      next: (lista) => {
        this.datasets.set(lista);
        this.carregando.set(false);
      },
      error: () => {
        this.carregando.set(false);
        this.erro.set('Não foi possível carregar os datasets.');
        this.notificationService.showError('Não foi possível carregar os datasets.');
      },
    });
  }
}
