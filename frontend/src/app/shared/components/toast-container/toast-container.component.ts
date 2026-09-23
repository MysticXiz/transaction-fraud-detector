import { Component, inject, OnInit } from '@angular/core';
import { AppNotification, NotificationService } from '../../../core/services/notification.service';

@Component({
  selector: 'app-toast-container',
  standalone: true,
  template: `
    <div class="toast-stack" aria-live="polite" aria-atomic="true">
      @for (item of notifications; track item.id) {
        <div class="toast toast-{{ item.type }}">
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
        color: #0f172a;
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
        color: #475569;
        font-size: 20px;
        line-height: 1;
        cursor: pointer;
      }
      .toast-close:hover { color: #0f172a; }
      .toast-success { background: #dcfce7; border-left: 4px solid #16a34a; }
      .toast-error { background: #fee2e2; border-left: 4px solid #dc2626; }
      .toast-info { background: #dbeafe; border-left: 4px solid #2563eb; }
      .toast-warning { background: #fef9c3; border-left: 4px solid #ca8a04; }
      .toast strong { font-size: 13px; }
      .toast span { font-size: 12.5px; }
    `,
  ],
})
export class ToastContainerComponent implements OnInit {
  private notificationService = inject(NotificationService);
  notifications: AppNotification[] = [];

  ngOnInit(): void {
    this.notificationService.notifications$.subscribe((item: AppNotification) => {
      if (!item.message && !item.title) {
        return;
      }
      this.notifications = [...this.notifications, item];
      if (item.duration) {
        setTimeout(() => {
          this.fechar(item.id);
        }, item.duration);
      }
    });
  }

  fechar(id: number): void {
    this.notifications = this.notifications.filter((item) => item.id !== id);
  }
}
