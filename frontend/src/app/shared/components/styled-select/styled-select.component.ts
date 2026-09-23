import { ElementRef, HostListener, Component, Input, forwardRef, signal } from '@angular/core';
import { ControlValueAccessor, NG_VALUE_ACCESSOR } from '@angular/forms';

export interface StyledSelectOption {
  valor: string;
  rotulo: string;
}

@Component({
  selector: 'app-styled-select',
  standalone: true,
  providers: [{ provide: NG_VALUE_ACCESSOR, useExisting: forwardRef(() => StyledSelectComponent), multi: true }],
  template: `
    <div class="select-wrapper">
      <button
        class="select-trigger"
        type="button"
        [attr.aria-expanded]="aberto()"
        aria-haspopup="listbox"
        (click)="alternar($event)"
        (keydown)="teclaNoGatilho($event)"
      >
        <span>{{ rotuloSelecionado() }}</span>
        <svg class="select-seta" [class.aberta]="aberto()" viewBox="0 0 24 24" aria-hidden="true">
          <path d="m7 9 5 5 5-5" />
        </svg>
      </button>

      @if (aberto()) {
        <div class="select-menu" role="listbox">
          @for (opcao of opcoes; track opcao.valor) {
            <button
              class="select-opcao"
              [class.selecionada]="opcao.valor === valor()"
              type="button"
              role="option"
              [attr.aria-selected]="opcao.valor === valor()"
              (click)="selecionar(opcao.valor)"
            >
              {{ opcao.rotulo }}
            </button>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    :host { display: block; width: 100%; }
    .select-wrapper { position: relative; }
    .select-trigger {
      width: 100%;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      padding: 10px 12px;
      border: 1px solid var(--cor-borda);
      border-radius: 8px;
      background: var(--cor-superficie);
      color: var(--cor-texto);
      font: inherit;
      font-size: 14px;
      text-align: left;
    }
    .select-trigger:hover, .select-trigger[aria-expanded='true'] { border-color: var(--cor-primaria); }
    .select-trigger:focus-visible, .select-opcao:focus-visible { outline: 2px solid #bfdbfe; outline-offset: 2px; }
    .select-seta { width: 16px; height: 16px; flex: 0 0 16px; fill: none; stroke: var(--cor-texto-suave); stroke-linecap: round; stroke-linejoin: round; stroke-width: 2; transition: transform .15s ease; }
    .select-seta.aberta { transform: rotate(180deg); }
    .select-menu {
      position: absolute;
      z-index: 20;
      top: calc(100% + 6px);
      left: 0;
      width: 100%;
      padding: 5px;
      border: 1px solid var(--cor-borda);
      border-radius: 8px;
      background: var(--cor-superficie);
      box-shadow: 0 12px 28px rgba(15, 23, 42, .2);
    }
    .select-opcao {
      display: block;
      width: 100%;
      padding: 9px 10px;
      border: 0;
      border-radius: 5px;
      background: transparent;
      color: var(--cor-texto);
      font: inherit;
      font-size: 14px;
      text-align: left;
    }
    .select-opcao:hover { background: var(--cor-superficie-suave); }
    .select-opcao.selecionada { background: var(--cor-primaria); color: #fff; }
  `],
})
export class StyledSelectComponent implements ControlValueAccessor {
  @Input({ required: true }) opcoes: StyledSelectOption[] = [];

  aberto = signal(false);
  valor = signal('');
  private desabilitado = false;
  private propagarMudanca: (valor: string) => void = () => undefined;
  private propagarToque: () => void = () => undefined;

  constructor(private elementRef: ElementRef<HTMLElement>) {}

  rotuloSelecionado(): string {
    return this.opcoes.find((opcao) => opcao.valor === this.valor())?.rotulo ?? '';
  }

  alternar(event: Event): void {
    event.stopPropagation();
    if (this.desabilitado) return;
    this.aberto.update((aberto) => !aberto);
    this.propagarToque();
  }

  selecionar(valor: string): void {
    this.valor.set(valor);
    this.propagarMudanca(valor);
    this.propagarToque();
    this.aberto.set(false);
  }

  teclaNoGatilho(event: KeyboardEvent): void {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      this.alternar(event);
    } else if (event.key === 'Escape') {
      this.aberto.set(false);
    }
  }

  @HostListener('document:click', ['$event'])
  fecharAoClicarFora(event: Event): void {
    if (!this.elementRef.nativeElement.contains(event.target as Node)) this.aberto.set(false);
  }

  writeValue(valor: string | number | null): void { this.valor.set(valor == null ? '' : String(valor)); }
  registerOnChange(fn: (valor: string) => void): void { this.propagarMudanca = fn; }
  registerOnTouched(fn: () => void): void { this.propagarToque = fn; }
  setDisabledState(desabilitado: boolean): void { this.desabilitado = desabilitado; }
}