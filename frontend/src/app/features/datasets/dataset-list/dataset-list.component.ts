import { DatePipe, DecimalPipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';
import { Dataset, DatasetDetalhe } from '../../../core/models/dataset.model';
import { DatasetService } from '../../../core/services/dataset.service';

const PAGE_SIZE = 50;

type SortColumn = 'nome' | 'origem' | 'total_registros' | 'importado_em';

@Component({
  selector: 'app-dataset-list',
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule, RouterLink],
  template: `
    <section class="dataset-page" aria-labelledby="page-title">
      <header class="page-header" aria-labelledby="page-title">
        <div class="page-header__copy">
          <p class="page-eyebrow">Biblioteca de dados</p>
          <h1 id="page-title" class="page-title">Datasets</h1>
          <p class="page-subtitle">Conjuntos de transações disponíveis para análise.</p>
        </div>
        <a routerLink="/datasets/importar" class="df-btn df-btn-primary">
          <span aria-hidden="true">+</span>
          Importar dataset
        </a>
      </header>

      @if (erroAcao()) {
        <div class="alerta erro" role="alert">
          <span>{{ erroAcao() }}</span>
          <button type="button" class="fechar-alerta" aria-label="Fechar aviso" (click)="erroAcao.set(null)">×</button>
        </div>
      }
      @if (sucessoAcao()) {
        <div class="alerta sucesso" role="status">
          <span>{{ sucessoAcao() }}</span>
          <button type="button" class="fechar-alerta" aria-label="Fechar aviso" (click)="sucessoAcao.set(null)">×</button>
        </div>
      }

      <div class="toolbar">
        <label class="busca">
          <span class="icone-busca" aria-hidden="true">⌕</span>
          <span class="visually-hidden">Buscar datasets</span>
          <input
            type="search"
            [(ngModel)]="termoBusca"
            placeholder="Buscar por nome ou origem"
            autocomplete="off"
          />
          @if (termoBusca) {
            <button type="button" class="limpar-busca" aria-label="Limpar busca" (click)="termoBusca = ''">×</button>
          }
        </label>
        <div class="resumo-lista" aria-live="polite">
          @if (carregando() && datasets().length === 0) {
            <span>Carregando…</span>
          } @else {
            <span>{{ resultadoBusca().length }} exibido(s)</span>
            @if (temMais()) { <span class="separador-resumo">·</span><span>{{ totalCarregado() }} carregado(s)</span> }
          }
        </div>
      </div>

      @if (carregando() && datasets().length === 0) {
        <div class="estado-inicial" role="status" aria-live="polite">
          <span class="spinner" aria-hidden="true"></span>
          <p>Carregando datasets</p>
        </div>
      } @else if (erroLista()) {
        <div class="estado-inicial estado-erro" role="alert">
          <h2>Não foi possível carregar os datasets</h2>
          <p>{{ erroLista() }}</p>
          <button class="df-btn df-btn-secundario" type="button" (click)="recarregar()">Tentar novamente</button>
        </div>
      } @else if (datasets().length === 0) {
        <div class="estado-inicial estado-vazio">
          <span class="icone-vazio" aria-hidden="true">▤</span>
          <h2>Nenhum dataset importado</h2>
          <p>Importe um arquivo CSV para disponibilizar transações no sistema.</p>
          <a routerLink="/datasets/importar" class="df-btn df-btn-primary">Importar primeiro dataset</a>
        </div>
      } @else if (resultadoBusca().length === 0) {
        <div class="estado-inicial estado-vazio">
          <h2>Nenhum resultado para “{{ termoBusca }}”</h2>
          <p>Revise o texto digitado ou limpe a busca.</p>
          <button type="button" class="df-btn df-btn-secundario" (click)="termoBusca = ''">Limpar busca</button>
        </div>
      } @else {
        <div class="tabela-wrap">
          <table class="tabela-datasets">
            <thead>
              <tr>
                <th scope="col">
                  <button type="button" class="ordenar" (click)="alternarOrdenacao('nome')" [attr.aria-sort]="ariaSort('nome')">
                    Dataset <span aria-hidden="true">{{ iconeOrdenacao('nome') }}</span>
                  </button>
                </th>
                <th scope="col">
                  <button type="button" class="ordenar" (click)="alternarOrdenacao('origem')" [attr.aria-sort]="ariaSort('origem')">
                    Origem <span aria-hidden="true">{{ iconeOrdenacao('origem') }}</span>
                  </button>
                </th>
                <th scope="col" class="numerica">
                  <button type="button" class="ordenar" (click)="alternarOrdenacao('total_registros')" [attr.aria-sort]="ariaSort('total_registros')">
                    Transações <span aria-hidden="true">{{ iconeOrdenacao('total_registros') }}</span>
                  </button>
                </th>
                <th scope="col">
                  <button type="button" class="ordenar" (click)="alternarOrdenacao('importado_em')" [attr.aria-sort]="ariaSort('importado_em')">
                    Importado em <span aria-hidden="true">{{ iconeOrdenacao('importado_em') }}</span>
                  </button>
                </th>
                <th scope="col" class="coluna-acoes">Ações</th>
              </tr>
            </thead>
            <tbody>
              @for (dataset of resultadoBusca(); track dataset.id_dataset) {
                <tr>
                  <td>
                    <div class="nome-dataset">{{ dataset.nome }}</div>
                    <div class="meta-dataset">{{ dataset.total_colunas }} colunas · {{ dataset.possui_rotulo ? 'rotulado' : 'sem rótulo' }}</div>
                  </td>
                  <td><span class="origem"><span class="ponto-origem" aria-hidden="true"></span>{{ dataset.origem || 'Não informada' }}</span></td>
                  <td class="numerica valor-registros">{{ dataset.total_registros | number: '1.0-0' : 'pt-BR' }}</td>
                  <td>
                    @if (dataset.importado_em) {
                      <time [attr.datetime]="dataset.importado_em">{{ dataset.importado_em | date: 'dd/MM/yyyy, HH:mm' }}</time>
                    } @else {
                      <span class="sem-data">Data indisponível</span>
                    }
                  </td>
                  <td class="coluna-acoes">
                    <div class="acoes-linha">
                      <button type="button" class="botao-analisar" (click)="analisar(dataset.id_dataset)">
                        <span aria-hidden="true">↗</span> Analisar
                      </button>
                      <button
                        type="button"
                        class="botao-icone"
                        [attr.aria-label]="(detalheAberto() === dataset.id_dataset ? 'Fechar' : 'Ver') + ' detalhes de ' + dataset.nome"
                        [attr.aria-expanded]="detalheAberto() === dataset.id_dataset"
                        (click)="alternarDetalhes(dataset.id_dataset)"
                        title="Detalhes"
                      >
                        <span aria-hidden="true">{{ detalheAberto() === dataset.id_dataset ? '−' : '⋯' }}</span>
                      </button>
                      <button
                        type="button"
                        class="botao-icone botao-excluir"
                        [disabled]="excluindoId() === dataset.id_dataset"
                        [attr.aria-label]="'Excluir dataset ' + dataset.nome"
                        (click)="excluir(dataset)"
                        title="Excluir"
                      >
                        <span aria-hidden="true">{{ excluindoId() === dataset.id_dataset ? '…' : '×' }}</span>
                      </button>
                    </div>
                  </td>
                </tr>
                @if (detalheAberto() === dataset.id_dataset) {
                  <tr class="linha-detalhe">
                    <td colspan="5">
                      @if (carregandoDetalheId() === dataset.id_dataset) {
                        <p class="estado-detalhe">Carregando amostra…</p>
                      } @else if (erroDetalhe()) {
                        <p class="erro-detalhe" role="alert">{{ erroDetalhe() }}</p>
                      } @else if (detalhe()) {
                        <div class="detalhe">
                          <div class="detalhe-cabecalho">
                            <div><span class="rotulo-detalhe">SHA-256</span><code>{{ detalhe()!.hash_arquivo }}</code></div>
                            @if (detalhe()!.descricao) { <p>{{ detalhe()!.descricao }}</p> }
                          </div>
                          <h3>Amostra das transações</h3>
                          @if (detalhe()!.amostra.length) {
                            <div class="amostra-wrap">
                              <table class="tabela-amostra">
                                <thead><tr><th>Índice</th><th>Tempo</th><th>Valor</th><th>Rótulo</th><th>Features</th></tr></thead>
                                <tbody>
                                  @for (linha of detalhe()!.amostra; track linha.indice_origem) {
                                    <tr>
                                      <td>{{ linha.indice_origem | number: '1.0-0' : 'pt-BR' }}</td>
                                      <td>{{ linha.tempo_relativo ?? '—' }}</td>
                                      <td>{{ linha.valor === null ? '—' : (linha.valor | number: '1.2-2' : 'pt-BR') }}</td>
                                      <td>{{ linha.rotulo_real === null ? '—' : (linha.rotulo_real ? 'Fraude' : 'Regular') }}</td>
                                      <td>{{ resumoFeatures(linha.atributos) }}</td>
                                    </tr>
                                  }
                                </tbody>
                              </table>
                            </div>
                          } @else {
                            <p class="estado-detalhe">Este dataset ainda não possui amostra disponível.</p>
                          }
                        </div>
                      }
                    </td>
                  </tr>
                }
              }
            </tbody>
          </table>
        </div>

        <footer class="rodape-lista">
          <span>Datas ordenados por {{ nomeOrdenacao() }}</span>
          @if (temMais()) {
            <button type="button" class="df-btn df-btn-secundario" [disabled]="carregandoMais()" (click)="carregarMais()">
              {{ carregandoMais() ? 'Carregando…' : 'Carregar mais' }}
            </button>
          } @else {
            <span class="fim-lista">Todos os datasets carregados</span>
          }
        </footer>
      }
    </section>
  `,
  styles: [`
    :host { display: block; }
    .dataset-page { max-width: 1240px; margin: 0 auto; }
    .toolbar { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 12px; }
    .busca { display: flex; align-items: center; gap: 9px; width: min(100%, 420px); min-height: 42px; padding: 0 12px; border: 1px solid var(--cor-borda); border-radius: 7px; background: var(--cor-superficie); }
    .busca:focus-within { outline: 2px solid #bfdbfe; border-color: var(--cor-primaria); }
    .icone-busca { color: var(--cor-texto-suave); font-size: 21px; transform: rotate(-20deg); }
    .busca input { flex: 1; min-width: 0; border: 0; outline: 0; background: transparent; color: var(--cor-texto); font: inherit; font-size: 13px; }
    .limpar-busca, .fechar-alerta { border: 0; background: transparent; color: var(--cor-texto-suave); font-size: 19px; cursor: pointer; }
    .resumo-lista { display: flex; gap: 7px; color: var(--cor-texto-suave); font-size: 12px; white-space: nowrap; }
    .separador-resumo { color: var(--cor-borda); }
    .tabela-wrap { overflow-x: auto; border: 1px solid var(--cor-borda); border-radius: 7px; background: var(--cor-superficie); }
    .tabela-datasets, .tabela-amostra { width: 100%; border-collapse: collapse; text-align: left; }
    .tabela-datasets th { height: 44px; padding: 0 16px; border-bottom: 1px solid var(--cor-borda); background: var(--cor-superficie-suave); color: var(--cor-texto-suave); font-size: 11px; font-weight: 700; text-transform: uppercase; white-space: nowrap; }
    .tabela-datasets td { height: 66px; padding: 10px 16px; border-bottom: 1px solid var(--cor-borda); font-size: 13px; white-space: nowrap; }
    .tabela-datasets tbody tr:last-child td { border-bottom: 0; }
    .tabela-datasets tbody tr:hover:not(.linha-detalhe) { background: var(--cor-superficie-suave); }
    .ordenar { display: inline-flex; align-items: center; gap: 5px; padding: 0; border: 0; background: none; color: inherit; font: inherit; text-transform: inherit; cursor: pointer; }
    .ordenar:hover { color: var(--cor-texto); }
    .numerica { text-align: right; font-variant-numeric: tabular-nums; }
    .valor-registros { font-weight: 600; }
    .nome-dataset { font-weight: 600; color: var(--cor-texto); }
    .meta-dataset { margin-top: 4px; color: var(--cor-texto-suave); font-size: 11px; }
    .origem { display: inline-flex; align-items: center; gap: 7px; }
    .ponto-origem { width: 7px; height: 7px; border-radius: 50%; background: #38a169; }
    .coluna-acoes { text-align: right; }
    .acoes-linha { display: inline-flex; align-items: center; justify-content: flex-end; gap: 5px; }
    .botao-analisar { display: inline-flex; align-items: center; gap: 5px; min-height: 32px; padding: 0 10px; border: 1px solid var(--cor-primaria); border-radius: 5px; background: transparent; color: var(--cor-primaria); font: inherit; font-size: 12px; font-weight: 600; cursor: pointer; }
    .botao-analisar:hover { background: var(--cor-primaria); color: white; }
    .botao-analisar:focus-visible, .botao-icone:focus-visible, .ordenar:focus-visible { outline: 2px solid #93c5fd; outline-offset: 2px; }
    .botao-icone { display: inline-grid; place-items: center; width: 32px; height: 32px; border: 1px solid transparent; border-radius: 5px; background: transparent; color: var(--cor-texto-suave); font-size: 18px; cursor: pointer; }
    .botao-icone:hover { border-color: var(--cor-borda); background: var(--cor-superficie-suave); color: var(--cor-texto); }
    .botao-excluir:hover { border-color: var(--cor-erro-texto); color: var(--cor-erro-texto); }
    .botao-icone:disabled { cursor: wait; opacity: .55; }
    .linha-detalhe td { height: auto; padding: 0; background: var(--cor-superficie-suave); }
    .detalhe { padding: 18px 20px 20px; }
    .detalhe-cabecalho { display: flex; flex-wrap: wrap; align-items: baseline; gap: 18px; margin-bottom: 18px; }
    .detalhe-cabecalho > div { display: grid; gap: 4px; }
    .rotulo-detalhe { color: var(--cor-texto-suave); font-size: 10px; font-weight: 700; text-transform: uppercase; }
    .detalhe code { color: var(--cor-texto); font-size: 11px; overflow-wrap: anywhere; }
    .detalhe h3 { margin: 0 0 9px; font-size: 13px; }
    .amostra-wrap { overflow-x: auto; border: 1px solid var(--cor-borda); border-radius: 5px; background: var(--cor-superficie); }
    .tabela-amostra th, .tabela-amostra td { height: auto; padding: 8px 10px; border-bottom: 1px solid var(--cor-borda); font-size: 11px; }
    .tabela-amostra th { color: var(--cor-texto-suave); font-weight: 600; }
    .tabela-amostra tr:last-child td { border-bottom: 0; }
    .estado-detalhe, .erro-detalhe { padding: 14px 18px; color: var(--cor-texto-suave); font-size: 12px; }
    .erro-detalhe { color: var(--cor-erro-texto); }
    .sem-data { color: var(--cor-texto-suave); font-size: 12px; }
    .rodape-lista { display: flex; justify-content: space-between; align-items: center; gap: 14px; padding: 14px 2px; color: var(--cor-texto-suave); font-size: 12px; }
    .fim-lista { margin-left: auto; }
    .estado-inicial { display: grid; justify-items: center; gap: 12px; padding: 64px 20px; border: 1px solid var(--cor-borda); border-radius: 7px; background: var(--cor-superficie); text-align: center; }
    .estado-inicial h2 { margin: 0; font-size: 17px; }
    .estado-inicial p { max-width: 440px; color: var(--cor-texto-suave); font-size: 13px; }
    .estado-erro { color: var(--cor-erro-texto); }
    .icone-vazio { color: var(--cor-texto-suave); font-size: 30px; }
    .spinner { width: 24px; height: 24px; border: 2px solid var(--cor-borda); border-top-color: var(--cor-primaria); border-radius: 50%; animation: girar .75s linear infinite; }
    .alerta { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; padding: 10px 12px; border-radius: 6px; font-size: 13px; }
    .alerta.erro { background: var(--cor-erro-bg); color: var(--cor-erro-texto); }
    .alerta.sucesso { background: var(--cor-sucesso-bg); color: var(--cor-sucesso-texto); }
    .alerta .fechar-alerta { color: inherit; }
    .visually-hidden { position: absolute; width: 1px; height: 1px; padding: 0; margin: -1px; overflow: hidden; clip: rect(0, 0, 0, 0); white-space: nowrap; border: 0; }
    @keyframes girar { to { transform: rotate(360deg); } }
    @media (max-width: 760px) {
      .toolbar { align-items: stretch; flex-direction: column; gap: 9px; }
      .busca { width: 100%; }
      .resumo-lista { justify-content: flex-end; }
      .tabela-datasets { min-width: 720px; }
      .rodape-lista { align-items: flex-start; flex-direction: column; }
      .fim-lista { margin-left: 0; }
    }
  `],
})
export class DatasetListComponent implements OnInit {
  private datasetService = inject(DatasetService);
  private router = inject(Router);

  datasets = signal<Dataset[]>([]);
  carregando = signal(true);
  carregandoMais = signal(false);
  erroLista = signal<string | null>(null);
  erroAcao = signal<string | null>(null);
  sucessoAcao = signal<string | null>(null);
  detalheAberto = signal<number | null>(null);
  detalhe = signal<DatasetDetalhe | null>(null);
  carregandoDetalheId = signal<number | null>(null);
  erroDetalhe = signal<string | null>(null);
  excluindoId = signal<number | null>(null);
  termoBusca = '';
  sortColumn = signal<SortColumn>('importado_em');
  sortDirection = signal<'asc' | 'desc'>('desc');
  totalCarregado = signal(0);
  temMais = signal(false);
  resultadoBusca = computed(() => {
    const query = this.termoBusca.trim().toLocaleLowerCase('pt-BR');
    const rows = this.datasets().filter((dataset) =>
      !query || `${dataset.nome} ${dataset.origem ?? ''}`.toLocaleLowerCase('pt-BR').includes(query),
    );
    const direction = this.sortDirection() === 'asc' ? 1 : -1;
    const column = this.sortColumn();
    return [...rows].sort((a, b) => {
      let comparison = 0;
      if (column === 'total_registros') comparison = a.total_registros - b.total_registros;
      else if (column === 'importado_em') comparison = Date.parse(a.importado_em) - Date.parse(b.importado_em);
      else comparison = String(a[column] ?? '').localeCompare(String(b[column] ?? ''), 'pt-BR');
      return comparison * direction;
    });
  });

  ngOnInit(): void {
    this.carregar();
  }

  carregar(): void {
    this.carregando.set(true);
    this.erroLista.set(null);
    this.datasetService.listar(0, PAGE_SIZE).pipe(finalize(() => this.carregando.set(false))).subscribe({
      next: (lista) => {
        this.datasets.set(lista);
        this.totalCarregado.set(lista.length);
        this.temMais.set(lista.length === PAGE_SIZE);
      },
      error: (error: unknown) => this.erroLista.set(this.mensagemErro(error)),
    });
  }

  recarregar(): void {
    this.carregar();
  }

  carregarMais(): void {
    if (this.carregandoMais() || !this.temMais()) return;
    this.carregandoMais.set(true);
    this.datasetService.listar(this.totalCarregado(), PAGE_SIZE).pipe(finalize(() => this.carregandoMais.set(false))).subscribe({
      next: (lista) => {
        this.datasets.update((atual) => [...atual, ...lista]);
        this.totalCarregado.update((atual) => atual + lista.length);
        this.temMais.set(lista.length === PAGE_SIZE);
      },
      error: (error: unknown) => this.erroAcao.set(this.mensagemErro(error)),
    });
  }

  alternarOrdenacao(column: SortColumn): void {
    if (this.sortColumn() === column) this.sortDirection.update((direction) => direction === 'asc' ? 'desc' : 'asc');
    else {
      this.sortColumn.set(column);
      this.sortDirection.set(column === 'importado_em' || column === 'total_registros' ? 'desc' : 'asc');
    }
  }

  ariaSort(column: SortColumn): 'ascending' | 'descending' | 'none' {
    if (this.sortColumn() !== column) return 'none';
    return this.sortDirection() === 'asc' ? 'ascending' : 'descending';
  }

  iconeOrdenacao(column: SortColumn): string {
    if (this.sortColumn() !== column) return '↕';
    return this.sortDirection() === 'asc' ? '↑' : '↓';
  }

  nomeOrdenacao(): string {
    const labels: Record<SortColumn, string> = {
      nome: 'nome',
      origem: 'origem',
      total_registros: 'número de transações',
      importado_em: 'data de importação',
    };
    return labels[this.sortColumn()];
  }

  analisar(datasetId: number): void {
    void this.router.navigate(['/analises/nova'], { queryParams: { datasetId } });
  }

  alternarDetalhes(datasetId: number): void {
    if (this.detalheAberto() === datasetId) {
      this.detalheAberto.set(null);
      this.detalhe.set(null);
      this.erroDetalhe.set(null);
      return;
    }
    this.detalheAberto.set(datasetId);
    this.detalhe.set(null);
    this.erroDetalhe.set(null);
    this.carregandoDetalheId.set(datasetId);
    this.datasetService.obter(datasetId).pipe(finalize(() => this.carregandoDetalheId.set(null))).subscribe({
      next: (detalhe) => this.detalhe.set(detalhe),
      error: (error: unknown) => this.erroDetalhe.set(this.mensagemErro(error)),
    });
  }

  resumoFeatures(features: Record<string, number>): string {
    const entries = Object.entries(features);
    if (!entries.length) return '—';
    const shown = entries.slice(0, 3).map(([name, value]) => `${name}: ${value}`);
    return `${shown.join(' · ')}${entries.length > 3 ? ` · +${entries.length - 3}` : ''}`;
  }

  excluir(dataset: Dataset): void {
    const confirmar = window.confirm(`Excluir o dataset “${dataset.nome}”? Esta ação não pode ser desfeita.`);
    if (!confirmar) return;
    this.excluindoId.set(dataset.id_dataset);
    this.erroAcao.set(null);
    this.sucessoAcao.set(null);
    this.datasetService.remover(dataset.id_dataset).pipe(finalize(() => this.excluindoId.set(null))).subscribe({
      next: () => {
        this.datasets.update((lista) => lista.filter((item) => item.id_dataset !== dataset.id_dataset));
        this.totalCarregado.update((total) => Math.max(0, total - 1));
        if (this.detalheAberto() === dataset.id_dataset) this.detalheAberto.set(null);
        this.sucessoAcao.set(`Dataset “${dataset.nome}” excluído.`);
      },
      error: (error: unknown) => this.erroAcao.set(this.mensagemErro(error)),
    });
  }

  private mensagemErro(error: unknown): string {
    if (!(error instanceof HttpErrorResponse)) return 'Ocorreu um erro inesperado.';
    if (error.status === 0) return 'Não foi possível conectar à API. Verifique se o backend está em execução.';
    if (typeof error.error?.detail === 'string') return error.error.detail;
    return `A operação falhou (HTTP ${error.status}).`;
  }
}
