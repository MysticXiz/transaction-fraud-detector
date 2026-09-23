import { PapelBenchmark } from './enums';

export interface BenchmarkConfiguracao {
  modo_execucao: 'SEQUENCIAL' | 'PARALELO';
  num_workers: number;
  rotulo: string;
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
  modo_execucao: string;
  num_workers: number;
  tempo_s: number;
  speedup: number;
  eficiencia: number;
}

export interface Benchmark {
  id_benchmark: number;
  id_dataset: number;
  dataset_nome: string;
  total_registros: number;
  descricao?: string;
  criado_em: string;
  status: 'PENDENTE' | 'EM_ANDAMENTO' | 'CONCLUIDO' | 'FALHA';
  execucoes: BenchmarkExecucaoItem[];
}
