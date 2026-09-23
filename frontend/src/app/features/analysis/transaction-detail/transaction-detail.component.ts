import { Component, OnInit, inject, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { DecimalPipe } from '@angular/common';
import { AnalysisService, DetalheTransacaoResponse } from '../../../core/services/analysis.service';

@Component({
  selector: 'app-transaction-detail',
  standalone: true,
  imports: [RouterLink, DecimalPipe],
  template: `
    <div class="cabecalho">
      <a [routerLink]="['/analises', idExecucao, 'resultados']" class="voltar">← Voltar aos Resultados</a>
      <h1>Transação #{{ idTransacao }}</h1>
    </div>

    @if (detalhe(); as d) {
      <div class="grid-topo">
        <div class="df-card">
          <h2 class="titulo-secao">Atributos da Transação</h2>
          <div class="atributos">
            <div><p class="rotulo">Tempo (Time)</p><p class="valor">{{ formatarHora(d.transacao.tempo_relativo) }}</p></div>
            <div><p class="rotulo">Valor (Amount)</p><p class="valor">\${{ d.transacao.valor | number: '1.2-2' : 'pt-BR' }}</p></div>
            @for (attr of amostraAtributos(d); track attr.key) {
              <div><p class="rotulo">{{ attr.key }}</p><p class="valor">{{ attr.value }}</p></div>
            }
          </div>
          <p class="atributos-ocultos">… demais atributos ocultos …</p>
          @if (d.transacao.rotulo_real != null) {
            <div class="rotulo-original">
              <p class="rotulo">Rótulo Original (Class)</p>
              <p class="valor" [class.cor-erro]="d.transacao.rotulo_real">
                {{ d.transacao.rotulo_real ? '1 (Fraude)' : '0 (Legítima)' }}
              </p>
            </div>
          }
        </div>

        <div class="df-card cartao-escore" [class.suspeita]="d.resultado_atual.is_suspeita">
          <p class="rotulo-escore">ESCORE ATRIBUÍDO</p>
          <p class="valor-escore" [class.cor-erro]="d.resultado_atual.is_suspeita">
            {{ d.resultado_atual.score_anomalia | number: '1.4-4' : 'pt-BR' }}
          </p>
          <p class="limiar">Limiar aplicado: {{ d.resultado_atual.limiar_aplicado }}</p>
          <span class="df-badge" [class]="d.resultado_atual.is_suspeita ? 'df-badge-erro' : 'df-badge-sucesso'">
            {{ d.resultado_atual.is_suspeita ? 'CLASSIFICADA COMO SUSPEITA' : 'CLASSIFICADA COMO LEGÍTIMA' }}
          </span>
        </div>
      </div>

      <div class="df-card">
        <h2 class="titulo-secao">Histórico de Avaliações (Verificação de Equivalência)</h2>
        <p class="descricao">Compara como esta mesma transação foi avaliada em execuções anteriores.</p>
        <table class="df-table">
          <thead>
            <tr>
              <th>Execução</th>
              <th>Modo</th>
              <th>Escore Calculado</th>
              <th>Equivalência</th>
            </tr>
          </thead>
          <tbody>
            @for (h of d.historico; track h.id_execucao) {
              <tr>
                <td>#{{ h.id_execucao }}</td>
                <td>{{ h.modo_execucao === 'SEQUENCIAL' ? 'Sequencial' : 'Paralelo (' + h.num_workers + ' workers)' }}</td>
                <td>{{ h.score_calculado | number: '1.4-4' : 'pt-BR' }}</td>
                <td>
                  @if (h.equivalente_ao_baseline === null) {
                    <span class="baseline">- Baseline -</span>
                  } @else if (h.equivalente_ao_baseline) {
                    <span class="identico">✔ Idêntico</span>
                  } @else {
                    <span class="cor-erro">✘ Divergente</span>
                  }
                </td>
              </tr>
            }
          </tbody>
        </table>
      </div>
    } @else if (erro()) {
      <p class="df-erro-msg">{{ erro() }}</p>
    }
  `,
  styles: [
    `
      .cabecalho { margin-bottom: 20px; }
      .voltar { font-size: 13.5px; color: var(--cor-texto-suave); display: inline-block; margin-bottom: 8px; }
      .cabecalho h1 { font-size: 22px; font-weight: 700; }
      .grid-topo { display: grid; grid-template-columns: 1.4fr 1fr; gap: 16px; margin-bottom: 16px; }
      .titulo-secao { font-size: 15px; font-weight: 700; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid var(--cor-borda); }
      .atributos { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
      .rotulo { font-size: 12px; color: var(--cor-texto-suave); margin-bottom: 4px; }
      .valor { font-size: 14.5px; font-weight: 600; font-family: monospace; }
      .atributos-ocultos { font-size: 12.5px; color: var(--cor-texto-suave); margin: 14px 0; }
      .rotulo-original { margin-top: 8px; }
      .cartao-escore { text-align: center; background: var(--cor-superficie); }
      .cartao-escore.suspeita { background: #fef2f2; }
      .rotulo-escore { font-size: 12px; font-weight: 700; color: var(--cor-erro-texto); letter-spacing: 0.4px; }
      .valor-escore { font-size: 34px; font-weight: 800; margin: 6px 0; }
      .limiar { font-size: 12.5px; color: var(--cor-texto-suave); margin-bottom: 14px; }
      .cor-erro { color: var(--cor-erro-texto); }
      .descricao { font-size: 13px; color: var(--cor-texto-suave); margin-bottom: 16px; }
      .identico { color: var(--cor-sucesso-texto); font-weight: 600; }
      .baseline { color: var(--cor-texto-suave); }
      @media (max-width: 900px) { .grid-topo { grid-template-columns: 1fr; } }
    `,
  ],
})
export class TransactionDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private analysisService = inject(AnalysisService);

  idExecucao = 0;
  idTransacao = 0;
  detalhe = signal<DetalheTransacaoResponse | null>(null);
  erro = signal<string | null>(null);

  ngOnInit(): void {
    this.idExecucao = Number(this.route.snapshot.paramMap.get('id'));
    this.idTransacao = Number(this.route.snapshot.paramMap.get('idTransacao'));

    this.analysisService.obterDetalheTransacao(this.idExecucao, this.idTransacao).subscribe({
      next: (d) => this.detalhe.set(d),
      error: () => this.erro.set('Não foi possível carregar o detalhe da transação.'),
    });
  }

  amostraAtributos(d: DetalheTransacaoResponse) {
    return Object.entries(d.transacao.atributos)
      .filter(([chave]) => chave !== 'Time' && chave !== 'Amount')
      .slice(0, 2)
      .map(([key, value]) => ({ key, value }));
  }

  formatarHora(tempoRelativo: number): string {
    const totalSegundos = Math.floor(tempoRelativo % 86400);
    const h = String(Math.floor(totalSegundos / 3600)).padStart(2, '0');
    const m = String(Math.floor((totalSegundos % 3600) / 60)).padStart(2, '0');
    const s = String(totalSegundos % 60).padStart(2, '0');
    return `${h}:${m}:${s}`;
  }
}
