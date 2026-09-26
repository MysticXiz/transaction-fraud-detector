import { TipoAlgoritmo } from './enums';

export interface Dataset {
  id_dataset: number;
  nome: string;
  descricao?: string;
  hash_arquivo: string;
  total_registros: number;
  total_colunas: number;
  origem: string | null;
  possui_rotulo: boolean;
  importado_em: string;
}

export interface DatasetTransacaoAmostra {
  indice_origem: number;
  valor: number | null;
  tempo_relativo: number | null;
  atributos: Record<string, number>;
  rotulo_real: boolean | null;
}

export interface DatasetDetalhe extends Dataset {
  amostra: DatasetTransacaoAmostra[];
}

export interface DatasetImportPayload {
  nome: string;
  origem: string;
  descricao?: string;
  arquivo: File;
}

export interface ModeloDeteccao {
  id_modelo: number;
  nome: string;
  algoritmo: TipoAlgoritmo;
  versao: string;
  limiar_padrao: number;
  treinado_em?: string;
}
