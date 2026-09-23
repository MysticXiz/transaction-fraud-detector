import { ModoExecucao, StatusExecucao } from './enums';

export interface ExecucaoAnaliseCreate {
  id_dataset: number;
  id_modelo: number;
  modo_execucao: ModoExecucao;
  num_workers: number;
  tamanho_chunk?: number;
  limiar_decisao?: number;
}

export interface ExecucaoAnalise {
  id_execucao: number;
  id_dataset: number;
  id_modelo: number;
  dataset_nome?: string;
  modelo_nome?: string;
  modo_execucao: ModoExecucao;
  num_workers: number;
  tamanho_chunk?: number;
  status: StatusExecucao;
  progresso_percentual?: number;
  iniciada_em?: string;
  finalizada_em?: string;
  tempo_total_s?: number;
  total_analisadas: number;
  total_suspeitas: number;
  mensagem_erro?: string;
}

export interface MetricaExecucao {
  tempo_leitura_s?: number;
  tempo_preproc_s?: number;
  tempo_inferencia_s?: number;
  tempo_overhead_s?: number;
  cpu_percent_medio?: number;
  memoria_pico_mb?: number;
  throughput_tps?: number;
  nucleos_disponiveis?: number;
}

export interface ResultadoDeteccao {
  id_resultado: number;
  id_execucao: number;
  id_transacao: number;
  score_anomalia: number;
  is_suspeita: boolean;
  limiar_aplicado: number;
  chunk_id?: number;
  valor?: number;
}

export interface AtributosTransacao {
  Time?: number;
  Amount?: number;
  [chave: string]: number | undefined;
}

export interface TransacaoDetalhe {
  id_transacao: number;
  indice_origem: number;
  valor: number;
  tempo_relativo: number;
  atributos: AtributosTransacao;
  rotulo_real?: boolean;
}

export interface AvaliacaoHistorico {
  id_execucao: number;
  modo_execucao: ModoExecucao;
  num_workers: number;
  score_calculado: number;
  equivalente_ao_baseline: boolean | null;
}

export interface ResultadosPage {
  execucao: ExecucaoAnalise;
  metrica: MetricaExecucao;
  itens: ResultadoDeteccao[];
  total: number;
  pagina: number;
  tamanho_pagina: number;
}
