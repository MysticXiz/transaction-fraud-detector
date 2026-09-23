import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize } from 'rxjs';
import { PapelUsuario } from '../../../core/models/enums';
import { AuthService } from '../../../core/services/auth.service';
import { NotificationService } from '../../../core/services/notification.service';
import { emailComDominioValido } from '../../../core/validators/email.validator';

@Component({
  selector: 'app-create-user',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="tela">
      <div class="cartao df-card">
        <div class="cabecalho">
          <div>
            <p class="eyebrow">Administração</p>
            <h1 class="titulo">Criar Usuário</h1>
          </div>
        </div>

        @if (etapa() === 'formulario') {
          <form class="etapa" [formGroup]="form" (ngSubmit)="continuar()">
            <label class="df-label" for="nome">Nome</label>
            <input id="nome" class="df-input" type="text" formControlName="nome" placeholder="Maria da Silva" />

            <label class="df-label campo-espaco" for="email">E-mail</label>
            <input id="email" class="df-input" type="email" formControlName="email" placeholder="usuario@sistema.com" (focus)="tocar('email')" />
            @if (form.controls.email.touched) {
              @if (!form.controls.email.value) {
                <small class="validacao validacao-erro">O e-mail é obrigatório.</small>
              } @else if (form.controls.email.invalid) {
                <small class="validacao validacao-erro">Digite um e-mail válido.</small>
              } @else {
                <small class="validacao validacao-sucesso">E-mail válido.</small>
              }
            }

            <label class="df-label campo-espaco" for="senha">Senha</label>
            <input id="senha" class="df-input" type="password" formControlName="senha" placeholder="••••••••" (focus)="tocar('senha')" />
            @if (form.controls.senha.touched) {
              @if (!form.controls.senha.value) {
                <small class="validacao validacao-erro">A senha é obrigatória.</small>
              } @else if (form.controls.senha.invalid) {
                <small class="validacao validacao-erro">A senha precisa ter no mínimo 8 caracteres.</small>
              } @else {
                <small class="validacao validacao-sucesso">Senha válida.</small>
              }
            }

            <label class="df-label campo-espaco" for="papel">Perfil</label>
            <select id="papel" class="df-input" formControlName="papel">
              <option [ngValue]="PapelUsuario.ADMIN">Administrador</option>
              <option [ngValue]="PapelUsuario.ANALISTA">Analista</option>
              <option [ngValue]="PapelUsuario.VISUALIZADOR">Visualizador</option>
            </select>

            @if (erro()) {
              <p class="df-erro-msg campo-erro">{{ erro() }}</p>
            }

            @if (sucesso()) {
                <div class="container-sucesso-msg">
                    <p class="df-sucesso-msg campo-erro">{{ sucesso() }}</p>
                </div>
              
            }

            <div class="acoes">
              <button type="button" class="df-btn df-btn-secundario" (click)="voltar()">Voltar</button>
              <button class="df-btn df-btn-primary" type="submit">Continuar</button>
            </div>
          </form>
        } @else {
          <section class="etapa confirmacao" aria-labelledby="titulo-confirmacao">
            <div class="confirmacao-cabecalho">
              <span class="indicador">2 de 2</span>
              <h2 id="titulo-confirmacao">Confirme as informações</h2>
              <p>Revise os dados antes de cadastrar o usuário.</p>
            </div>

            <dl class="resumo">
              <div class="resumo-item">
                <dt>Nome</dt>
                  <dd>{{ valor('nome') }}</dd>
              </div>
              <div class="resumo-item">
                <dt>E-mail</dt>
                <dd>{{ valor('email') }}</dd>
              </div>
              <div class="resumo-item">
                <dt>Perfil</dt>
                <dd [class.perfil-admin]="form.controls.papel.value === PapelUsuario.ADMIN">{{ nomePapel() }}</dd>
              </div>
            </dl>

            @if (erro()) {
              <p class="df-erro-msg campo-erro">{{ erro() }}</p>
            }

            <div class="acoes">
              <button type="button" class="df-btn df-btn-secundario" (click)="voltarParaEdicao()" [disabled]="carregando()">Voltar</button>
              <button class="df-btn df-btn-primary" type="button" (click)="criar()" [disabled]="carregando()">
                {{ carregando() ? 'Cadastrando…' : 'Cadastrar Usuário' }}
              </button>
            </div>
          </section>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .tela {
        min-height: calc(100vh - 64px);
        display: flex;
        align-items: center;
        justify-content: center;
      }
      .cartao {
        width: min(100%, 560px);
      }
      .container-sucesso-msg{
        display: flex;
        align-items: center;
        justify-content: center;
        background-color: var(--cor-sucesso-bg);
        padding: 10px 20px;
        margin-top: 10px;
        border-radius: 4px;
      }
      .container-sucesso-msg p{
        color: var(--cor-sucesso-texto);
        margin: 0;
      }
      .cabecalho {
        margin-bottom: 20px;
      }
      .eyebrow {
        margin: 0 0 6px;
        font-size: 12px;
        text-transform: uppercase;
        letter-spacing: 0.12em;
        color: #7dd3fc;
        font-weight: 700;
      }
      .titulo {
        font-size: 26px;
        font-weight: 700;
        margin: 0;
      }
      .campo-espaco {
        margin-top: 16px;
      }
      .campo-erro {
        margin-top: 14px;
      }
      .validacao {
        display: block;
        margin-top: 5px;
        font-size: 12px;
      }
      .validacao-erro { color: #dc2626; }
      .validacao-sucesso { color: #16a34a; }
      .etapa {
        animation: entrar-etapa 180ms ease-out;
      }
      .confirmacao-cabecalho {
        margin-bottom: 20px;
      }
      .indicador {
        display: inline-block;
        margin-bottom: 8px;
        color: #7dd3fc;
        font-size: 12px;
        font-weight: 700;
        letter-spacing: 0.08em;
        text-transform: uppercase;
      }
      .confirmacao h2 {
        margin: 0;
        font-size: 22px;
      }
      .confirmacao-cabecalho p {
        margin: 8px 0 0;
        color: #94a3b8;
        font-size: 14px;
      }
      .resumo {
        display: grid;
        gap: 10px;
        margin: 0;
      }
      .resumo-item {
        display: flex;
        align-items: baseline;
        justify-content: space-between;
        gap: 16px;
        padding: 12px 14px;
        border: 1px solid var(--cor-borda);
        border-radius: 8px;
        background: var(--cor-superficie-suave);
      }
      .resumo-item dt {
        color: var(--cor-texto-suave);
        font-size: 13px;
      }
      .resumo-item dd {
        margin: 0;
        color: var(--cor-texto);
        font-size: 14px;
        font-weight: 600;
        text-align: right;
        overflow-wrap: anywhere;
      }
      .resumo-item dd.perfil-admin {
        color: var(--cor-sucesso-texto);
      }
      @keyframes entrar-etapa {
        from {
          opacity: 0;
          transform: translateX(12px);
        }
        to {
          opacity: 1;
          transform: translateX(0);
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .etapa {
          animation: none;
        }
      }
      .acoes {
        display: flex;
        gap: 12px;
        margin-top: 24px;
      }
      .acoes button {
        flex: 1;
      }
      @media (max-width: 540px) {
        .acoes {
          flex-direction: column;
        }
      }
    `,
  ],
})
export class CreateUserComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);
  private notifications = inject(NotificationService);

  readonly PapelUsuario = PapelUsuario;
  carregando = signal(false);
  erro = signal<string | null>(null);
  sucesso = signal<string | null>(null);
  // A etapa mantém o formulário montado logicamente para permitir edição sem perder os dados.
  etapa = signal<'formulario' | 'confirmacao'>('formulario');

  form = this.fb.nonNullable.group({
    nome: ['', [Validators.required, Validators.minLength(3)]],
    email: ['', [Validators.required, Validators.email, emailComDominioValido]],
    senha: ['', [Validators.required, Validators.minLength(8)]],
    papel: [PapelUsuario.ANALISTA, [Validators.required]],
  });

  tocar(campo: 'email' | 'senha'): void {
    this.form.controls[campo].markAsTouched();
  }

  continuar(): void {
    // A confirmação só aparece depois que todos os campos foram validados localmente.
    this.form.markAllAsTouched();
    if (this.form.invalid) return;

    this.erro.set(null);
    this.sucesso.set(null);
    this.etapa.set('confirmacao');
  }

  criar(): void {
    if (this.form.invalid) {
      this.etapa.set('formulario');
      return;
    }

    this.carregando.set(true);
    this.erro.set(null);
    this.sucesso.set(null);

    this.auth
      .registrar(this.form.getRawValue())
      .pipe(finalize(() => this.carregando.set(false)))
      .subscribe({
        next: (usuario) => {
          // A resposta da API é usada na confirmação para não exibir dados diferentes dos persistidos.
          const mensagem = `#${usuario.id_usuario} · ${usuario.nome} · ${usuario.email} · Perfil: ${this.rotuloPapel(usuario.papel)}`;
          this.sucesso.set(`Usuário ${usuario.nome} cadastrado com sucesso.`);
          this.notifications.showSuccess(mensagem, 'Usuário criado');
          this.etapa.set('formulario');
          this.form.reset({
            nome: '',
            email: '',
            senha: '',
            papel: PapelUsuario.ANALISTA,
          });
        },
        error: (err) => {
          const mensagem = err?.status === 403
            ? 'Você não tem permissão para criar usuários.'
            : this.mensagemErroApi(err) || 'Não foi possível criar o usuário.';
          this.erro.set(mensagem);
        },
      });
  }

  voltar(): void {
    this.router.navigateByUrl('/dashboard');
  }

  voltarParaEdicao(): void {
    this.erro.set(null);
    this.etapa.set('formulario');
  }

  valor(campo: 'nome' | 'email' | 'papel'): string {
    return this.form.controls[campo].value;
  }

  nomePapel(): string {
    return this.rotuloPapel(this.form.controls.papel.value);
  }

  private rotuloPapel(papel: PapelUsuario): string {
    const papeis: Record<PapelUsuario, string> = {
      [PapelUsuario.ADMIN]: 'Administrador',
      [PapelUsuario.ANALISTA]: 'Analista',
      [PapelUsuario.VISUALIZADOR]: 'Visualizador',
    };
    return papeis[papel];
  }

  private mensagemErroApi(err: { error?: { detail?: string | Array<{ msg?: string }> } }): string | null {
    const detalhe = err.error?.detail;
    if (typeof detalhe === 'string') return detalhe;
    if (Array.isArray(detalhe)) {
      return detalhe
        .map((item) => item.msg)
        .filter((mensagem): mensagem is string => Boolean(mensagem))
        .join(' ');
    }
    return null;
  }
}
