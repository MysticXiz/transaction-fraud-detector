import { Component, Input, computed, signal } from '@angular/core';
import { StatusExecucao } from '../../../core/models/enums';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  template: `<span class="df-badge" [class]="classe()">{{ rotulo() }}</span>`,
})
export class StatusBadgeComponent {
  private statusSignal = signal<StatusExecucao | string>(StatusExecucao.PENDENTE);

  @Input({ required: true })
  set status(valor: StatusExecucao | string) {
    this.statusSignal.set(valor);
  }

  rotulo = computed(() => {
    switch (this.statusSignal()) {
      case StatusExecucao.CONCLUIDA:
        return 'Concluída';
      case StatusExecucao.EM_ANDAMENTO:
        return 'A decorrer';
      case StatusExecucao.PENDENTE:
        return 'Pendente';
      case StatusExecucao.FALHA:
        return 'Falha';
      case StatusExecucao.CANCELADA:
        return 'Cancelada';
      default:
        return String(this.statusSignal());
    }
  });

  classe = computed(() => {
    switch (this.statusSignal()) {
      case StatusExecucao.CONCLUIDA:
        return 'df-badge-sucesso';
      case StatusExecucao.EM_ANDAMENTO:
        return 'df-badge-aviso';
      case StatusExecucao.FALHA:
        return 'df-badge-erro';
      default:
        return 'df-badge-neutro';
    }
  });
}
