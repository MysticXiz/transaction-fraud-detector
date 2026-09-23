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
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(16, 24, 40, 0.08);
        padding: 20px 24px;
      }
      .rotulo {
        font-size: 13px;
        color: #6b7280;
        margin-bottom: 6px;
      }
      .valor {
        font-size: 26px;
        font-weight: 700;
        color: var(--df-card color);
      }
    `,
  ],
})
export class StatCardComponent {
  @Input({ required: true }) rotulo!: string;
  @Input({ required: true }) valor!: string | number;
}
