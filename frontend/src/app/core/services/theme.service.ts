import { Injectable, signal } from '@angular/core';

const THEME_KEY = 'df_theme';

@Injectable({ providedIn: 'root' })
export class ThemeService {
  escuro = signal(false);

  constructor() {
    // O tema é restaurado antes da primeira interação para manter a preferência entre sessões.
    this.escuro.set(localStorage.getItem(THEME_KEY) === 'dark');
    this.aplicarTema();
  }

  alternar(): void {
    this.escuro.update((valor) => !valor);
    // A classe no elemento raiz permite que componentes isolados compartilhem as mesmas variáveis CSS.
    localStorage.setItem(THEME_KEY, this.escuro() ? 'dark' : 'light');
    this.aplicarTema();
  }

  private aplicarTema(): void {
    document.documentElement.classList.toggle('tema-escuro', this.escuro());
  }
}
