import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { environment } from '../../../environments/environment';
import { Usuario } from '../models/usuario.model';

interface ConfiguracaoUploads {
  limite_bytes: number;
  maximo_mib: number;
}

type PermissoesUsuario = Pick<Usuario, 'papel' | 'ativo'>;

@Injectable({ providedIn: 'root' })
export class ServerAdminService {
  private http = inject(HttpClient);
  private uploadsUrl = `${environment.apiUrl}/admin/configuracoes/uploads`;
  private usersUrl = `${environment.apiUrl}/auth/users`;

  obterUploads() {
    return this.http.get<ConfiguracaoUploads>(this.uploadsUrl);
  }

  salvarUploads(limite_mib: number) {
    return this.http.put<ConfiguracaoUploads>(this.uploadsUrl, { limite_mib });
  }

  listarUsuarios() {
    return this.http.get<Usuario[]>(this.usersUrl);
  }

  atualizarUsuario(id: number, permissoes: PermissoesUsuario) {
    return this.http.put<Usuario>(`${this.usersUrl}/${id}`, permissoes);
  }

  excluirUsuario(id: number) {
    return this.http.delete<void>(`${this.usersUrl}/${id}`);
  }
}
