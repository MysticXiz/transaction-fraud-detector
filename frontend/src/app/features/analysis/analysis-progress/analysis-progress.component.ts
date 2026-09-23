import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { interval, startWith, switchMap } from 'rxjs';
import { AnalysisService } from '../../../core/services/analysis.service';
import { StatusExecucao } from '../../../core/models/enums';

@Component({
  selector: 'app-analysis-progress',
  standalone: true,
  template: `
    <div class="wrapper">
      <div class="df-card cartao">
        <h2 class="titulo">{{ tituloEstado() }}</h2>
        <div class="barra-fundo">
          <div class="barra-preenchida" [style.width.%]="progresso()"></div>
        </div>
        @if (erro()) {
          <p class="df-erro-msg" style="margin-top:16px">{{ erro() }}</p>
          <button class="df-btn df-btn-secundario" style="margin-top:16px" (click)="voltar()">
            Voltar para Configuração
          </button>
        }
      </div>
    </div>
  `,
  styles: [
    `
      .wrapper { display: flex; justify-content: center; padding-top: 96px; }
      .cartao { width: 420px; text-align: center; }
      .titulo { font-size: 18px; font-weight: 700; margin-bottom: 18px; }
      .barra-fundo { background: #e5e7eb; border-radius: 999px; height: 8px; overflow: hidden; }
      .barra-preenchida {
        background: var(--cor-primaria);
        height: 100%;
        border-radius: 999px;
        transition: width 0.4s ease;
      }
    `,
  ],
})
export class AnalysisProgressComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private analysisService = inject(AnalysisService);
  private destroyRef = inject(DestroyRef);

  progresso = signal(15);
  erro = signal<string | null>(null);
  status = signal<StatusExecucao>(StatusExecucao.PENDENTE);

  tituloEstado(): string {
    switch (this.status()) {
      case StatusExecucao.CONCLUIDA:
        return 'Análise concluída, redirecionando…';
      case StatusExecucao.FALHA:
        return 'Falha ao processar a análise';
      default:
        return 'Processando Análise…';
    }
  }

  ngOnInit(): void {
    const idExecucao = Number(this.route.snapshot.paramMap.get('id'));

    interval(1500)
      .pipe(
        startWith(0),
        switchMap(() => this.analysisService.obterStatus(idExecucao)),
        takeUntilDestroyed(this.destroyRef)
      )
      .subscribe({
        next: (execucao) => {
          this.status.set(execucao.status);
          this.progresso.set(execucao.progresso_percentual ?? (execucao.status === StatusExecucao.CONCLUIDA ? 100 : 45));

          if (execucao.status === StatusExecucao.CONCLUIDA) {
            this.router.navigate(['/analises', idExecucao, 'resultados']);
          } else if (execucao.status === StatusExecucao.FALHA) {
            this.erro.set(execucao.mensagem_erro ?? 'A execução falhou.');
          }
        },
        error: () => this.erro.set('Não foi possível consultar o andamento da análise.'),
      });
  }

  voltar(): void {
    this.router.navigateByUrl('/analises/nova');
  }
}
