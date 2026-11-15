import { Injectable } from '@angular/core';
import { Subject } from 'rxjs';

export type NotificationType = 'success' | 'error' | 'info' | 'warning';

export interface AppNotification {
  id: number;
  type: NotificationType;
  title: string;
  message: string;
  duration?: number;
}

@Injectable({ providedIn: 'root' })
export class NotificationService {
  // Um Subject mantém o toast desacoplado da tela que originou a notificação.
  private notificationsSubject = new Subject<AppNotification>();
  private counter = 0;

  readonly notifications$ = this.notificationsSubject.asObservable();

  showSuccess(message: string, title = 'Sucesso'): void {
    // Mensagens de sucesso ficam mais tempo disponíveis porque contêm dados do usuário criado.
    this.push({ type: 'success', title, message, duration: 8000 });
  }

  showError(message: string, title = 'Erro'): void {
    this.push({ type: 'error', title, message, duration: 5000 });
  }

  showInfo(message: string, title = 'Aviso'): void {
    this.push({ type: 'info', title, message, duration: 4000 });
  }

  showWarning(message: string, title = 'Atenção'): void {
    this.push({ type: 'warning', title, message, duration: 4000 });
  }

  dismiss(id: number): void {
    this.notificationsSubject.next({ id, type: 'info', title: '', message: '', duration: 0 });
  }

  private push(notification: Omit<AppNotification, 'id'>): void {
    this.notificationsSubject.next({ id: ++this.counter, ...notification });
  }
}
