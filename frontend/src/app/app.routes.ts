import { Routes } from '@angular/router';
import { adminGuard } from './core/guards/admin.guard';
import { authGuard } from './core/guards/auth.guard';
import { ShellComponent } from './layout/shell/shell.component';

export const routes: Routes = [
  {
    path: 'login',
    loadComponent: () => import('./features/auth/login/login.component').then((m) => m.LoginComponent),
    title: 'Login · Detecção de Fraude',
  },
  {
    path: '',
    component: ShellComponent,
    canActivate: [authGuard],
    children: [
      { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
      {
        path: 'dashboard',
        loadComponent: () =>
          import('./features/dashboard/dashboard.component').then((m) => m.DashboardComponent),
        title: 'Visão Geral · Detecção de Fraude',
      },
      {
        path: 'datasets',
        loadComponent: () =>
          import('./features/datasets/dataset-list/dataset-list.component').then(
            (m) => m.DatasetListComponent
          ),
        title: 'Datasets · Detecção de Fraude',
      },
      {
        path: 'datasets/importar',
        loadComponent: () =>
          import('./features/datasets/dataset-import/dataset-import.component').then(
            (m) => m.DatasetImportComponent
          ),
        title: 'Importar Dataset · Detecção de Fraude',
      },
      {
        path: 'analises/nova',
        loadComponent: () =>
          import('./features/analysis/analysis-config/analysis-config.component').then(
            (m) => m.AnalysisConfigComponent
          ),
        title: 'Configurar Análise · Detecção de Fraude',
      },
      {
        path: 'analises/:id/execucao',
        loadComponent: () =>
          import('./features/analysis/analysis-progress/analysis-progress.component').then(
            (m) => m.AnalysisProgressComponent
          ),
        title: 'Executando Análise · Detecção de Fraude',
      },
      {
        path: 'analises/:id/resultados',
        loadComponent: () =>
          import('./features/analysis/analysis-results/analysis-results.component').then(
            (m) => m.AnalysisResultsComponent
          ),
        title: 'Resultados · Detecção de Fraude',
      },
      {
        path: 'analises/:id/resultados/:idTransacao',
        loadComponent: () =>
          import('./features/analysis/transaction-detail/transaction-detail.component').then(
            (m) => m.TransactionDetailComponent
          ),
        title: 'Detalhe da Transação · Detecção de Fraude',
      },
      {
        path: 'benchmark',
        loadComponent: () =>
          import('./features/benchmark/benchmark-config/benchmark-config.component').then(
            (m) => m.BenchmarkConfigComponent
          ),
        title: 'Executar Benchmark · Detecção de Fraude',
      },
      {
        path: 'benchmark/:id/relatorio',
        loadComponent: () =>
          import('./features/benchmark/benchmark-report/benchmark-report.component').then(
            (m) => m.BenchmarkReportComponent
          ),
        title: 'Relatório de Benchmark · Detecção de Fraude',
      },
      {
        path: 'historico',
        loadComponent: () => import('./features/history/history.component').then((m) => m.HistoryComponent),
        title: 'Histórico de Execuções · Detecção de Fraude',
      },
      {
        path: 'minha-conta',
        loadComponent: () =>
          import('./features/account/account.component').then((m) => m.AccountComponent),
        title: 'Minha Conta · Detecção de Fraude',
      },
      {
        path: 'admin/usuarios/novo',
        loadComponent: () =>
          import('./features/admin/create-user/create-user.component').then(
            (m) => m.CreateUserComponent
          ),
        title: 'Criar Usuário · Detecção de Fraude',
        canActivate: [adminGuard],
      },
    ],
  },
  { path: '**', redirectTo: 'dashboard' },
];
