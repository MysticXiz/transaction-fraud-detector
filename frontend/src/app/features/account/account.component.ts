import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  ValidatorFn,
  Validators,
} from '@angular/forms';
import { finalize } from 'rxjs';
import { AuthService } from '../../core/services/auth.service';
import { emailComDominioValido } from '../../core/validators/email.validator';

const senhasIguais: ValidatorFn = (control: AbstractControl): ValidationErrors | null => {
  const senha = control.get('senha')?.value;
  const confirmarSenha = control.get('confirmarSenha')?.value;
  return senha === confirmarSenha ? null : { senhasDiferentes: true };
};

@Component({
  selector: 'app-account',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="tela">
      <section class="cabecalho-secao">
        <p class="eyebrow">Segurança da conta</p>
        <h1>Minha conta</h1>
        <p class="descricao">Atualize seus dados de acesso e mantenha seu perfil em dia.</p>
      </section>

      <div class="grade">
        <section class="cartao df-card">
          <div class="cabecalho-cartao">
            <div>
              <h2>Dados pessoais</h2>
              <p>Essas informações identificam você no sistema.</p>
            </div>
            <span class="status" [class.status-inativo]="!auth.usuario()?.ativo">
              {{ auth.usuario()?.ativo ? 'Conta ativa' : 'Conta inativa' }}
            </span>
          </div>

          <form [formGroup]="form" (ngSubmit)="salvar()" novalidate>
            <label class="df-label" for="nome">Nome</label>
            <input id="nome" class="df-input" type="text" formControlName="nome" autocomplete="name" />
            @if (form.controls.nome.touched && form.controls.nome.invalid) {
              <small class="validacao validacao-erro">Informe um nome com pelo menos 2 caracteres.</small>
            }

            <label class="df-label campo-espaco" for="email">E-mail</label>
            <input id="email" class="df-input" type="email" formControlName="email" autocomplete="email" />
            @if (form.controls.email.touched) {
              @if (!form.controls.email.value) {
                <small class="validacao validacao-erro">O e-mail é obrigatório.</small>
              } @else if (form.controls.email.invalid) {
                <small class="validacao validacao-erro">Digite um e-mail válido.</small>
              }
            }

            <div class="divisor"></div>
            <div class="subcabecalho">
              <h2>Alterar senha</h2>
              <p>Deixe os campos em branco para manter sua senha atual.</p>
            </div>

            <label class="df-label campo-espaco" for="senha">Nova senha</label>
            <input id="senha" class="df-input" type="password" formControlName="senha" autocomplete="new-password" />
            @if (form.controls.senha.touched && form.controls.senha.value && form.controls.senha.invalid) {
              <small class="validacao validacao-erro">A senha precisa ter no mínimo 8 caracteres.</small>
            }

            <label class="df-label campo-espaco" for="confirmarSenha">Confirmar nova senha</label>
            <input id="confirmarSenha" class="df-input" type="password" formControlName="confirmarSenha" autocomplete="new-password" />
            @if (form.controls.confirmarSenha.touched && form.controls.confirmarSenha.value && form.errors?.['senhasDiferentes']) {
              <small class="validacao validacao-erro">As senhas precisam ser iguais.</small>
            }

            @if (erro()) {
              <p class="df-erro-msg mensagem">{{ erro() }}</p>
            }
            @if (sucesso()) {
              <p class="df-sucesso-msg mensagem">{{ sucesso() }}</p>
            }

            <div class="acoes">
              <button class="df-btn df-btn-secundario" type="button" (click)="restaurar()" [disabled]="carregando()">Descartar</button>
              <button class="df-btn df-btn-primary" type="submit" [disabled]="carregando()">
                {{ carregando() ? 'Salvando...' : 'Salvar alterações' }}
              </button>
            </div>
          </form>
        </section>

        <aside class="cartao df-card resumo">
          <p class="eyebrow">Informações da conta</p>
          <dl>
            <div><dt>Perfil</dt><dd>{{ rotuloPapel() }}</dd></div>
            <div><dt>Status</dt><dd>{{ auth.usuario()?.ativo ? 'Ativo' : 'Inativo' }}</dd></div>
            <div><dt>Membro desde</dt><dd>{{ dataCriacao() }}</dd></div>
          </dl>
          <p class="nota">Sua senha nunca é exibida e só é alterada quando você preencher os dois campos de senha.</p>
        </aside>
      </div>
    </div>
  `,
  styles: [
    `
      .tela { max-width: 980px; margin: 0 auto; }
      .cabecalho-secao { margin-bottom: 24px; }
      .eyebrow { color: var(--cor-primaria); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 7px; }
      h1 { font-size: 30px; line-height: 1.15; }
      .descricao { color: var(--cor-texto-suave); margin-top: 8px; }
      .grade { display: grid; grid-template-columns: minmax(0, 1.55fr) minmax(230px, .8fr); gap: 20px; align-items: start; }
      .cabecalho-cartao { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 22px; }
      h2 { font-size: 18px; }
      .cabecalho-cartao p, .subcabecalho p { color: var(--cor-texto-suave); font-size: 13px; margin-top: 5px; }
      .status { white-space: nowrap; color: var(--cor-sucesso-texto); background: var(--cor-sucesso-bg); border-radius: 999px; padding: 5px 9px; font-size: 12px; font-weight: 700; }
      .status-inativo { color: var(--cor-erro-texto); background: var(--cor-erro-bg); }
      .campo-espaco { margin-top: 17px; }
      .validacao { display: block; margin-top: 5px; font-size: 12px; }
      .validacao-erro { color: var(--cor-erro-texto); }
      .divisor { border-top: 1px solid var(--cor-borda); margin: 28px 0 22px; }
      .subcabecalho h2 { font-size: 16px; }
      .mensagem { margin-top: 18px; }
      .df-sucesso-msg { background: var(--cor-sucesso-bg); color: var(--cor-sucesso-texto); border-radius: 8px; padding: 10px 14px; font-size: 13px; }
      .acoes { display: flex; justify-content: flex-end; gap: 10px; margin-top: 24px; }
      .resumo { padding: 22px; }
      .resumo dl { display: grid; gap: 15px; margin: 22px 0; }
      .resumo dl div { display: flex; justify-content: space-between; gap: 12px; border-bottom: 1px solid var(--cor-borda); padding-bottom: 12px; }
      dt { color: var(--cor-texto-suave); font-size: 13px; }
      dd { margin: 0; font-size: 13px; font-weight: 700; text-align: right; overflow-wrap: anywhere; }
      .nota { color: var(--cor-texto-suave); font-size: 12px; line-height: 1.5; }
      @media (max-width: 760px) {
        .grade { grid-template-columns: 1fr; }
        .cabecalho-cartao { flex-direction: column; }
      }
      @media (max-width: 520px) {
        .acoes { flex-direction: column-reverse; }
        .acoes button { width: 100%; justify-content: center; }
      }
    `,
  ],
})
export class AccountComponent {
  readonly auth = inject(AuthService);
  private readonly fb = inject(FormBuilder);
  carregando = signal(false);
  erro = signal<string | null>(null);
  sucesso = signal<string | null>(null);

  form = this.fb.nonNullable.group(
    {
      nome: [this.auth.usuario()?.nome ?? '', [Validators.required, Validators.minLength(2), Validators.maxLength(120)]],
      email: [this.auth.usuario()?.email ?? '', [Validators.required, Validators.email, emailComDominioValido]],
      senha: ['', [Validators.minLength(8), Validators.maxLength(255)]],
      confirmarSenha: [''],
    },
    { validators: senhasIguais }
  );

  salvar(): void {
    this.form.markAllAsTouched();
    this.erro.set(null);
    this.sucesso.set(null);
    if (this.form.invalid) return;

    const usuario = this.auth.usuario();
    if (!usuario) return;

    const valores = this.form.getRawValue();
    const payload: { nome?: string; email?: string; senha?: string } = {};
    if (valores.nome.trim() !== usuario.nome) payload.nome = valores.nome.trim();
    if (valores.email.trim().toLowerCase() !== usuario.email.toLowerCase()) payload.email = valores.email.trim();
    if (valores.senha) payload.senha = valores.senha;

    if (!Object.keys(payload).length) {
      this.sucesso.set('Nenhuma alteração nova para salvar.');
      return;
    }

    this.carregando.set(true);
    this.auth.atualizarPerfil(payload).pipe(finalize(() => this.carregando.set(false))).subscribe({
      next: () => {
        this.form.patchValue({ senha: '', confirmarSenha: '' });
        this.form.markAsPristine();
        this.sucesso.set('Dados da conta atualizados com sucesso.');
      },
      error: (err) => this.erro.set(this.mensagemErroApi(err) ?? 'Não foi possível atualizar sua conta.'),
    });
  }

  restaurar(): void {
    const usuario = this.auth.usuario();
    if (!usuario) return;
    this.form.reset({ nome: usuario.nome, email: usuario.email, senha: '', confirmarSenha: '' });
    this.erro.set(null);
    this.sucesso.set(null);
  }

  rotuloPapel(): string {
    const papeis: Record<string, string> = { ADMIN: 'Administrador', ANALISTA: 'Analista', VISUALIZADOR: 'Visualizador' };
    return papeis[this.auth.usuario()?.papel ?? ''] ?? this.auth.usuario()?.papel ?? '-';
  }

  dataCriacao(): string {
    const data = this.auth.usuario()?.criado_em;
    return data ? new Intl.DateTimeFormat('pt-BR').format(new Date(data)) : '-';
  }

  private mensagemErroApi(err: { error?: { detail?: string | Array<{ msg?: string }> } }): string | null {
    const detalhe = err.error?.detail;
    if (typeof detalhe === 'string') return detalhe;
    if (Array.isArray(detalhe)) return detalhe.map((item) => item.msg).filter(Boolean).join(' ') || null;
    return null;
  }
}
