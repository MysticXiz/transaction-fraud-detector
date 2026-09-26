import { registerLocaleData } from '@angular/common';
import { bootstrapApplication } from '@angular/platform-browser';
import localePtBr from '@angular/common/locales/pt';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

registerLocaleData(localePtBr, 'pt-BR');

bootstrapApplication(AppComponent, appConfig).catch((err) => console.error(err));
