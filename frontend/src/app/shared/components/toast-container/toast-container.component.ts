import { Component, DestroyRef, inject, OnInit } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AppNotification, NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-toast-container',
  standalone: true,
  template: `
    <div class="toast-stack" aria-live="polite" aria-atomic="true">
      @for (item of notifications; track item.id) {
        <div class="toast toast-{{ item.type }}" [attr.role]="item.type === 'error' ? 'alert' : 'status'">
          <div class="toast-content">
            <strong>{{ item.title }}</strong>
            <span>{{ item.message }}</span>
          </div>
          <button type="button" class="toast-close" (click)="fechar(item.id)" [attr.aria-label]="'Fechar notificação: ' + item.title">×</button>
        </div>
      }
    </div>
  `,
  styles: [
    `
      .toast-stack {
        position: fixed;
        right: 20px;
        bottom: 20px;
        display: flex;
        flex-direction: column;
        gap: 10px;
        z-index: 1000;
      }
      .toast {
        min-width: 260px;
        max-width: 360px;
        padding: 12px 14px;
        border-radius: 10px;
        box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 12px;
        color: var(--cor-texto);
        background: var(--cor-superficie);
      }
      .toast-content {
        display: flex;
        flex-direction: column;
        gap: 4px;
      }
      .toast-close {
        flex: 0 0 auto;
        border: 0;
        padding: 0;
        background: transparent;
        color: var(--cor-texto-suave);
        font-size: 20px;
        line-height: 1;
        cursor: pointer;
      }
      .toast-close:hover { color: var(--cor-texto); }
      .toast-success { background: var(--cor-sucesso-bg); border-left: 4px solid var(--cor-sucesso-texto); }
      .toast-error { background: var(--cor-erro-bg); border-left: 4px solid var(--cor-erro-texto); }
      .toast-info { background: var(--cor-info-bg); border-left: 4px solid var(--cor-info-texto); }
      .toast-warning { background: var(--cor-aviso-bg); border-left: 4px solid var(--cor-aviso-texto); }
      .toast strong { font-size: 13px; }
      .toast span { font-size: 12.5px; }
    `,
  ],
})
export class ToastContainerComponent implements OnInit {
  private notificationService = inject(NotificationService);
  private destroyRef = inject(DestroyRef);
  notifications: AppNotification[] = [];
  private timers = new Map<number, ReturnType<typeof setTimeout>>();

  constructor() {
    this.destroyRef.onDestroy(() => {
      for (const timer of this.timers.values()) clearTimeout(timer);
      this.timers.clear();
    });
  }

  ngOnInit(): void {
    this.notificationService.notifications$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe((item: AppNotification) => {
        if (!item.message && !item.title) {
          this.remover(item.id);
          return;
        }
        this.notifications = [...this.notifications, item];
        if (item.duration) {
          this.timers.set(item.id, setTimeout(() => this.fechar(item.id), item.duration));
        }
      });
  }

  fechar(id: number): void {
    this.remover(id);
    this.notificationService.dismiss(id);
  }

  private remover(id: number): void {
    const timer = this.timers.get(id);
    if (timer !== undefined) {
      clearTimeout(timer);
      this.timers.delete(id);
    }
    this.notifications = this.notifications.filter((item) => item.id !== id);
  }
}
