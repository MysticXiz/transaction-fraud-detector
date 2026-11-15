import { PapelBenchmark } from './enums';

export interface BenchmarkConfiguracao {
  modo_execucao: 'SEQUENCIAL' | 'PARALELO';
  work_group_size: number;
  rotulo: string;
  tipo_dispositivo?: 'CPU' | 'GPU' | null;
}

export interface BenchmarkCreate {
  id_dataset: number;
  id_modelo: number;
  configuracoes: BenchmarkConfiguracao[];
}

export interface BenchmarkExecucaoItem {
  id_benchmark_exec: number;
  id_execucao: number;
  papel: PapelBenchmark;
  tipo_dispositivo: 'CPU' | 'GPU' | null;
  modo_execucao: string;
  work_group_size: number;
  tempo_s: number | null;
  tempo_inferencia_s: number | null;
  speedup: number | null;
  eficiencia: number | null;
}

export interface Benchmark {
  id_benchmark: number;
  id_dataset: number;
  dataset_nome: string;
  total_registros: number;
  descricao?: string;
  criado_em: string;
  status:
    | 'PENDENTE'
    | 'EM_ANDAMENTO'
    | 'CANCELAMENTO_SOLICITADO'
    | 'CONCLUIDO'
    | 'FALHA'
    | 'CANCELADO';
  mensagem_erro?: string | null;
  execucoes: BenchmarkExecucaoItem[];
}
