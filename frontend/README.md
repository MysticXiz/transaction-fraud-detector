# Detecção de Fraude — Frontend (Angular 22)

Frontend standalone (Angular 22, signals, novo control-flow `@if`/`@for`) que reproduz as
11 telas prototipadas no documento técnico (Sprint 02, seção 5) e já está preparado para
consumir a API FastAPI descrita nas Sprints 02/03 do projeto.

> ⚠️ Este ambiente de geração não tem acesso à internet, então o `node_modules` **não foi
> instalado**. Rode `npm install` na sua máquina antes de usar o projeto.

## Como rodar

```bash
npm install
npm start          # ng serve, abre em http://localhost:4200
```

Configure a URL do backend em `src/environments/environment.ts` (dev) e
`environment.production.ts` (build de produção). Por padrão aponta para
`http://127.0.0.1:8000`, igual ao exemplo de execução do Sprint 03
(`uvicorn src.fraud_detector.main:app --reload`).

## Estrutura

```
src/app/
├── core/
│   ├── models/        # Usuario, Dataset, ExecucaoAnalise, ResultadoDeteccao, Benchmark, enums…
│   ├── services/       # AuthService, DatasetService, AnalysisService, BenchmarkService
│   ├── interceptors/    # authInterceptor (anexa Bearer JWT, trata 401)
│   └── guards/          # authGuard (protege as rotas internas)
├── layout/shell/        # Sidebar fixa "Detecção de Fraude" + <router-outlet>
├── shared/components/    # StatCard, StatusBadge
└── features/
    ├── auth/login                          → T01 Login
    ├── dashboard                           → T02 Dashboard
    ├── datasets/dataset-import             → T03 Importar Dataset
    ├── datasets/dataset-list               → T04 Datasets
    ├── analysis/analysis-config            → T05 Configurar Análise
    ├── analysis/analysis-progress          → T06 Execução em Andamento
    ├── analysis/analysis-results           → T07 Resultados da Análise
    ├── analysis/transaction-detail         → T08 Detalhe da Transação
    ├── benchmark/benchmark-config          → T09 Executar Benchmark
    ├── benchmark/benchmark-report          → T10 Relatório Comparativo
    └── history                             → T11 Histórico de Execuções
```

Todas as telas usam `loadComponent` (lazy-loading por rota) — ver `app.routes.ts`, que
reproduz o mapa de navegação da seção 5.1 do documento.

## Contrato de API assumido

Os serviços em `core/services` foram escritos a partir da arquitetura documentada
(routers `/datasets`, `/analises`, `/benchmarks`, `/resultados`, autenticação JWT em
`/auth`). Como o backend ainda está em desenvolvimento, seguem os endpoints/payloads
que o frontend espera — ajuste os nomes/campos no backend (ou nos services, se preferir
manter o contrato do backend) para que fiquem idênticos:

### Autenticação (`/auth`)
| Método | Rota | Body | Resposta |
|---|---|---|---|
| POST | `/auth/login` | `{ email, senha }` | `{ access_token, token_type }` |
| POST | `/auth/register` | `{ nome, email, senha, papel? }` | `Usuario` (somente ADMIN, conforme Sprint 03) |
| GET | `/auth/me` | — | `Usuario` |

### Datasets (`/datasets`) — RF01/RF02
| Método | Rota | Body | Resposta |
|---|---|---|---|
| GET | `/datasets` | — | `Dataset[]` |
| GET | `/datasets/{id}` | — | `Dataset` |
| POST | `/datasets` | `multipart/form-data`: `nome`, `origem`, `descricao?`, `arquivo` | `Dataset` |
| DELETE | `/datasets/{id}` | — | `204` |
| GET | `/modelos` | — | `ModeloDeteccao[]` (Isolation Forest, Regressão Logística…) |

### Análises (`/analises`) — RF04/RF05/RF06/RF08/RF09
| Método | Rota | Body | Resposta |
|---|---|---|---|
| POST | `/analises` | `{ id_dataset, id_modelo, modo_execucao, num_workers, tamanho_chunk?, limiar_decisao? }` | `202 Accepted` + `ExecucaoAnalise` (status `PENDENTE`) |
| GET | `/analises/{id}` | — | `ExecucaoAnalise` (usado em polling na tela T06; inclua `progresso_percentual` se possível) |
| POST | `/analises/{id}/cancelar` | — | `204` |
| GET | `/analises/{id}/resultados?pagina&tamanho_pagina&escore_minimo&valor_minimo` | — | `{ execucao, metrica, itens, total, pagina, tamanho_pagina }` |
| GET | `/analises/{id}/resultados/exportar?formato=csv\|json` | — | arquivo (blob) |
| GET | `/analises/{idExecucao}/resultados/{idTransacao}` | — | `{ transacao, resultado_atual, historico }` — `historico` traz a verificação de equivalência sequencial × paralelo (T08) |
| GET | `/analises?status&modo_execucao` | — | `ExecucaoAnalise[]` (histórico, T11) |

### Benchmark (`/benchmarks`) — RF09/PB12
| Método | Rota | Body | Resposta |
|---|---|---|---|
| POST | `/benchmarks` | `{ id_dataset, id_modelo, configuracoes: [{ modo_execucao, num_workers, rotulo }] }` | `Benchmark` |
| GET | `/benchmarks/{id}` | — | `Benchmark` com `execucoes[]` (tempo, speedup, eficiência) |
| GET | `/benchmarks/{id}/exportar` | — | PDF (blob) |

Os modelos completos (`Usuario`, `Dataset`, `ExecucaoAnalise`, `ResultadoDeteccao`,
`Benchmark` etc.) estão em `src/app/core/models/*.model.ts`, espelhando as entidades do
MER/modelo relacional (Sprint 02, seções 2–4).

## Autenticação

O JWT retornado por `/auth/login` é salvo em `localStorage` (`df_access_token`) e
anexado automaticamente em toda requisição via `authInterceptor`. Um retorno `401`
desloga o usuário e redireciona para `/login`. As rotas internas (tudo dentro do
`ShellComponent`) são protegidas por `authGuard`.

## Próximos ajustes recomendados

- Alinhar nomes de campos com o schema real do backend (Pydantic/SQLAlchemy) assim que
  os endpoints estiverem prontos — os `interface`s TypeScript concentram tudo isso.
- Se o backend expuser progresso real da execução (via WebSocket/SSE em vez de polling),
  trocar o `interval()` de `analysis-progress.component.ts` pela stream correspondente.
- Adicionar testes (Jasmine/Karma ou Vitest) e CI, conforme `PB17` do backlog.
