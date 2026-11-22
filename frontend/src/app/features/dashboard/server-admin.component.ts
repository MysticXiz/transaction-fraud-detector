import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { Observable, finalize } from 'rxjs';
import { PapelUsuario } from '../../core/models/enums';
import { Usuario } from '../../core/models/usuario.model';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { ServerAdminService } from '../../core/services/server-admin.service';

@Component({
  selector: 'app-server-admin',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="df-pagina">
      <header class="page-header">
        <h1 class="page-title">Configurações do servidor</h1>
        <a routerLink="/dashboard" class="df-btn df-btn-secundario">Voltar ao dashboard</a>
      </header>

      <section class="df-card painel" aria-labelledby="uploads-titulo">
        <h2 id="uploads-titulo">Uploads de datasets</h2>
        <p>O limite vale para cada arquivo CSV enviado por qualquer usuário.</p>
        @if (maximoMib(); as maximo) {
          <form (ngSubmit)="salvarLimite()">
            <label for="limite-upload" class="df-label">Limite por arquivo (MiB)</label>
            <div class="acoes">
              <input id="limite-upload" name="limite" class="df-input" type="number"
                [(ngModel)]="limiteMib" min="1" [max]="maximo" step="1"
                [disabled]="salvandoLimite()" required />
              <button class="df-btn df-btn-primary" type="submit"
                [disabled]="!limiteValido() || salvandoLimite()">Salvar limite</button>
            </div>
          </form>
        } @else if (!erroUploads()) {
          <p role="status">Carregando limite de upload…</p>
        }
        @if (erroUploads(); as erro) {
          <p role="alert">{{ erro }}</p>
        }
      </section>

      <section class="df-card painel" aria-labelledby="usuarios-titulo">
        <div class="cabecalho">
          <h2 id="usuarios-titulo">Gerenciar usuários</h2>
          <a routerLink="/dashboard/servidor/usuarios/novo" class="df-btn df-btn-primary">Criar usuário</a>
        </div>
        @if (erroUsuarios(); as erro) {
          <p role="alert">{{ erro }}</p>
        }
        @if (usuarios(); as lista) {
          <div class="tabela-scroll">
            <table>
              <thead>
                <tr><th scope="col">Conta</th><th scope="col">Perfil</th><th scope="col">Ativa</th><th scope="col">Ações</th></tr>
              </thead>
              <tbody>
                @for (usuario of lista; track usuario.id_usuario) {
                  <tr>
                    <td><strong>{{ usuario.nome }}</strong><br />{{ usuario.email }}</td>
                    <td>
                      <select #papel class="df-input"
                        [disabled]="!podeGerenciar(usuario)" [attr.aria-label]="'Perfil de ' + usuario.nome">
                        @for (opcao of papeis; track opcao) {
                          <option [value]="opcao" [selected]="opcao === usuario.papel">{{ opcao }}</option>
                        }
                      </select>
                    </td>
                    <td>
                      <input #ativo type="checkbox" [checked]="usuario.ativo"
                        [disabled]="!podeGerenciar(usuario)" [attr.aria-label]="'Conta ativa de ' + usuario.nome" />
                    </td>
                    <td>
                      @if (usuario.id_usuario === auth.usuario()?.id_usuario) {
                        Sua conta
                      } @else {
                        <div class="acoes">
                          <button class="df-btn df-btn-secundario" type="button" [disabled]="!podeGerenciar(usuario)"
                            (click)="salvarUsuario(usuario, papel.value, ativo.checked)">Salvar</button>
                          <button class="df-btn df-btn-secundario" type="button" [disabled]="!podeGerenciar(usuario)"
                            (click)="excluirUsuario(usuario)">Excluir</button>
                        </div>
                      }
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        } @else if (!erroUsuarios()) {
          <p role="status">Carregando usuários…</p>
        }
      </section>
    </div>
  `,
  styles: `
    .painel { margin-top: 16px; }
    .painel p { margin: 8px 0 16px; }
    .cabecalho, .acoes { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
    .cabecalho { justify-content: space-between; margin-bottom: 14px; }
    .acoes .df-input { width: 10rem; }
    .tabela-scroll { overflow-x: auto; }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th, td { padding: 12px; border-bottom: 1px solid var(--cor-borda); }
  `,
})
export class ServerAdminComponent implements OnInit {
  protected auth = inject(AuthService);
  private admin = inject(ServerAdminService);
  private notifications = inject(NotificationService);

  papeis = Object.values(PapelUsuario);
  usuarios = signal<Usuario[] | null>(null);
  maximoMib = signal<number | null>(null);
  limiteMib: number | null = null;
  salvandoLimite = signal(false);
  usuarioEmAlteracao = signal<number | null>(null);
  erroUploads = signal<string | null>(null);
  erroUsuarios = signal<string | null>(null);

  ngOnInit(): void {
    this.admin.obterUploads().subscribe({
      next: (config) => {
        this.maximoMib.set(config.maximo_mib);
        this.limiteMib = config.limite_bytes / (1024 * 1024);
      },
      error: () => this.erroUploads.set('Não foi possível consultar o limite de upload.'),
    });
    this.admin.listarUsuarios().subscribe({
      next: (usuarios) => this.usuarios.set(usuarios),
      error: () => this.erroUsuarios.set('Não foi possível carregar os usuários.'),
    });
  }

  limiteValido(): boolean {
    const limite = this.limiteMib;
    return limite !== null && Number.isInteger(limite) && limite >= 1 && limite <= (this.maximoMib() ?? 0);
  }

  salvarLimite(): void {
    if (this.limiteMib === null || !this.limiteValido() || this.salvandoLimite()) return;
    this.salvandoLimite.set(true);
    this.erroUploads.set(null);
    this.admin.salvarUploads(this.limiteMib).pipe(finalize(() => this.salvandoLimite.set(false)))
      .subscribe({
        next: () => this.notifications.showSuccess('Limite de upload atualizado.'),
        error: () => this.erroUploads.set('Não foi possível salvar o limite de upload.'),
      });
  }

  podeGerenciar(usuario: Usuario): boolean {
    return usuario.id_usuario !== this.auth.usuario()?.id_usuario && this.usuarioEmAlteracao() === null;
  }

  salvarUsuario(usuario: Usuario, papel: string, ativo: boolean): void {
    const perfil = this.papeis.find((opcao) => opcao === papel);
    if (!perfil || !this.podeGerenciar(usuario)) return;
    this.executarAlteracao(usuario, this.admin.atualizarUsuario(usuario.id_usuario, { papel: perfil, ativo }),
      (atualizado) => this.usuarios.update((lista) => lista?.map((item) =>
        item.id_usuario === atualizado.id_usuario ? atualizado : item) ?? null));
  }

  excluirUsuario(usuario: Usuario): void {
    if (!this.podeGerenciar(usuario) || !window.confirm(`Excluir a conta de ${usuario.nome}?`)) return;
    this.executarAlteracao(usuario, this.admin.excluirUsuario(usuario.id_usuario),
      () => this.usuarios.update((lista) => lista?.filter((item) => item.id_usuario !== usuario.id_usuario) ?? null));
  }

  private executarAlteracao<T>(usuario: Usuario, acao: Observable<T>, concluir: (resultado: T) => void): void {
    this.usuarioEmAlteracao.set(usuario.id_usuario);
    this.erroUsuarios.set(null);
    acao.pipe(finalize(() => this.usuarioEmAlteracao.set(null))).subscribe({
      next: (resultado) => {
        concluir(resultado);
        this.notifications.showSuccess('Lista de usuários atualizada.');
      },
      error: (erro) => this.erroUsuarios.set(typeof erro.error?.detail === 'string'
        ? erro.error.detail : 'Não foi possível alterar a conta.'),
    });
  }
}
