import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { Router } from '@angular/router';
import { finalize, switchMap } from 'rxjs';
import { AuthService } from '../../../core/services/auth.service';
import { emailComDominioValido } from '../../../core/validators/email.validator';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [ReactiveFormsModule],
  template: `
    <div class="tela">
      <div class="cartao df-card">
        <p class="eyebrow">Acesso seguro</p>
        <h1 class="titulo">Acesso ao Sistema</h1>
        <form [formGroup]="form" (ngSubmit)="entrar()">
          <label class="df-label" for="email">E-mail</label>
          <input id="email" class="df-input" type="email" formControlName="email" placeholder="admin@sistema.com" (focus)="tocar('email')" />
          @if (form.controls.email.touched) {
            @if (!form.controls.email.value) {
              <small class="validacao validacao-erro">O e-mail é obrigatório.</small>
            } @else if (form.controls.email.invalid) {
              <small class="validacao validacao-erro">Digite um e-mail válido.</small>
            } @else {
              <small class="validacao validacao-sucesso">E-mail válido.</small>
            }
          }

          <label class="df-label campo-senha" for="senha">Senha</label>
          <input id="senha" class="df-input" type="password" formControlName="senha" placeholder="••••••••" (focus)="tocar('senha')" />
          @if (form.controls.senha.touched) {
            @if (!form.controls.senha.value) {
              <small class="validacao validacao-erro">A senha é obrigatória.</small>
            } @else {
              <small class="validacao validacao-sucesso">Senha preenchida.</small>
            }
          }

          @if (erro()) {
            <div class="df-alerta df-alerta-erro campo-erro" role="alert">
              <span>{{ erro() }}</span>
              <button type="button" class="df-alerta-fechar" aria-label="Fechar aviso" (click)="erro.set(null)">×</button>
            </div>
          }

          <button class="df-btn df-btn-primary botao" type="submit" [disabled]="form.invalid || carregando()">
            @if (carregando()) {
              <span class="df-spinner" aria-hidden="true"></span> Entrando…
            } @else {
              Acessar
            }
          </button>
        </form>
      </div>
    </div>
  `,
  styles: [
    `
      .tela {
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
        background: var(--cor-fundo);
      }
      .cartao { width: 360px; }
      .eyebrow { color: var(--cor-primaria); font-size: 12px; font-weight: 700; letter-spacing: .12em; text-transform: uppercase; margin-bottom: 7px; }
      .titulo { font-size: 22px; font-weight: 700; margin-bottom: 22px; }
      .campo-senha { margin-top: 16px; }
      .campo-erro { margin-top: 14px; }
      .validacao {
        display: block;
        margin-top: 5px;
        font-size: 12px;
      }
      .validacao-erro { color: #dc2626; }
      .validacao-sucesso { color: #16a34a; }
      .botao { width: 100%; justify-content: center; margin-top: 22px; padding: 11px; }
    `,
  ],
})
export class LoginComponent {
  private fb = inject(FormBuilder);
  private auth = inject(AuthService);
  private router = inject(Router);

  carregando = signal(false);
  erro = signal<string | null>(null);

  form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email, emailComDominioValido]],
    senha: ['', [Validators.required, Validators.minLength(6)]],
  });

  tocar(campo: 'email' | 'senha'): void {
    this.form.controls[campo].markAsTouched();
  }

  entrar(): void {
    if (this.form.invalid) return;
    this.carregando.set(true);
    this.erro.set(null);

    this.auth
      .login(this.form.getRawValue())
      .pipe(
        switchMap(() => this.auth.carregarPerfil()),
        finalize(() => this.carregando.set(false))
      )
      .subscribe({
        next: () => {
          this.router.navigateByUrl('/dashboard');
        },
        error: (err) => {
          this.auth.logout();
          this.erro.set(err?.status === 401 ? 'E-mail ou senha inválidos.' : 'Não foi possível acessar o sistema.');
        },
      });
  }
}
