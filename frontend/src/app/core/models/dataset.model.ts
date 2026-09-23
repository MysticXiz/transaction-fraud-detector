import { TipoAlgoritmo } from './enums';

export interface Dataset {
  id_dataset: number;
  nome: string;
  descricao?: string;
  hash_arquivo: string;
  total_registros: number;
  total_colunas: number;
  origem: string;
  possui_rotulo: boolean;
  importado_em: string;
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
