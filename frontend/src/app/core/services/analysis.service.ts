import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import {
  AvaliacaoHistorico,
  ExecucaoAnalise,
  ExecucaoAnaliseCreate,
  ResultadosPage,
  TransacaoDetalhe,
} from '../models/analise.model';
import { ModoExecucao, StatusExecucao } from '../models/enums';

export interface HistoricoFiltro {
  status?: StatusExecucao | 'TODOS';
  modo?: ModoExecucao | 'TODOS';
}

export interface ResultadosFiltro {
  escoreMinimo?: number;
  valorMinimo?: number;
  suspeita?: boolean;
}

export interface DetalheTransacaoResponse {
  transacao: TransacaoDetalhe;
  resultado_atual: {
    id_execucao: number;
    score_anomalia: number;
    limiar_aplicado: number;
    is_suspeita: boolean;
  };
  historico: AvaliacaoHistorico[];
}

@Injectable({ providedIn: 'root' })
export class AnalysisService {
  private http = inject(HttpClient);
  private baseUrl = `${environment.apiUrl}/analises`;

  /** Enfileira a execução no backend. A API responde 202 Accepted. */
  executar(payload: ExecucaoAnaliseCreate) {
    return this.http.post<ExecucaoAnalise>(this.baseUrl, payload);
  }

  /** Consulta de status/progresso — usada em polling na tela de execução em andamento (T06). */
  obterStatus(idExecucao: number) {
    return this.http.get<ExecucaoAnalise>(`${this.baseUrl}/${idExecucao}`);
  }

  cancelar(idExecucao: number) {
    return this.http.post<void>(`${this.baseUrl}/${idExecucao}/cancelar`, {});
  }

  remover(idExecucao: number) {
    return this.http.delete<void>(`${this.baseUrl}/${idExecucao}`);
  }

  limparHistorico() {
    return this.http.delete<{ removidas: number; preservadas_em_andamento: number }>(
      `${this.baseUrl}/historico`
    );
  }

  /** Resultados paginados e ordenados por escore (RF06/RF07/RF08). */
  obterResultados(
    idExecucao: number,
    opts: ResultadosFiltro & { pagina?: number; tamanhoPagina?: number } = {}
  ) {
    const params = this.parametrosResultados(opts)
      .set('pagina', String(opts.pagina ?? 1))
      .set('tamanho_pagina', String(opts.tamanhoPagina ?? 25));
    return this.http.get<ResultadosPage>(`${this.baseUrl}/${idExecucao}/resultados`, { params });
  }

  urlExportacao(idExecucao: number, formato: 'csv' | 'json', filtro: ResultadosFiltro) {
    const params = this.parametrosResultados(filtro).set('formato', formato);
    return `${this.baseUrl}/${idExecucao}/resultados/exportar?${params}`;
  }

  private parametrosResultados(opts: ResultadosFiltro): HttpParams {
    let params = new HttpParams();
    if (opts.escoreMinimo != null) params = params.set('escore_minimo', opts.escoreMinimo);
    if (opts.valorMinimo != null) params = params.set('valor_minimo', opts.valorMinimo);
    if (opts.suspeita != null) params = params.set('is_suspeita', opts.suspeita);
    return params;
  }

  /** Detalhe de uma transação + histórico de avaliações (verificação de equivalência sequencial x paralelo). */
  obterDetalheTransacao(idExecucao: number, idTransacao: number) {
    return this.http.get<DetalheTransacaoResponse>(
      `${this.baseUrl}/${idExecucao}/resultados/${idTransacao}`
    );
  }

  /** Histórico de execuções (UC05/T11), com filtros por status e modo. */
  listarHistorico(filtro: HistoricoFiltro = {}) {
    let params = new HttpParams();
    if (filtro.status && filtro.status !== 'TODOS') params = params.set('status', filtro.status);
    if (filtro.modo && filtro.modo !== 'TODOS') params = params.set('modo_execucao', filtro.modo);
    return this.http.get<ExecucaoAnalise[]>(this.baseUrl, { params });
  }
}
