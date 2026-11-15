import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-stat-card',
  standalone: true,
  template: `
    <div class="card">
      <p class="rotulo">{{ rotulo }}</p>
      <p class="valor">{{ valor }}</p>
    </div>
  `,
  styles: [
    `
      .card {
        background: var(--cor-superficie);
        border: 1px solid var(--cor-borda);
        border-radius: var(--raio);
        padding: 20px 24px;
      }
      .rotulo {
        font-size: 13px;
        color: var(--cor-texto-suave);
        margin-bottom: 6px;
      }
      .valor {
        font-size: 26px;
        font-weight: 700;
        color: var(--cor-texto);
      }
    `,
  ],
})
export class StatCardComponent {
  @Input({ required: true }) rotulo!: string;
  @Input({ required: true }) valor!: string | number;
}
