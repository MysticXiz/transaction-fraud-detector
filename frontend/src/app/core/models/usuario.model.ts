import { PapelUsuario } from './enums';

export interface Usuario {
  id_usuario: number;
  nome: string;
  email: string;
  papel: PapelUsuario;
  ativo: boolean;
  criado_em: string;
}

export interface LoginRequest {
  email: string;
  senha: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface RegisterRequest {
  nome: string;
  email: string;
  senha: string;
  papel?: PapelUsuario;
}
