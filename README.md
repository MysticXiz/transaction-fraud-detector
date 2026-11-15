# Detector de Fraudes em Transações

## Visão geral

Sistema full-stack para importação de datasets, detecção de transações suspeitas, acompanhamento de análises e execução de benchmarks com OpenCL.

- **Backend**: FastAPI, SQLAlchemy 2, PostgreSQL e PyOpenCL
- **Frontend**: Angular 22, RxJS e TypeScript
- **Banco**: PostgreSQL 16
- **Infraestrutura**: Docker Compose, Nginx e volumes persistentes

## Objetivo da solução

O sistema permite que analistas de fraude importem datasets de transações financeiras, configurem e executem análises de detecção de anomalias usando Isolation Forest (com aceleração OpenCL), visualizem resultados detalhados com métricas de performance, e realizem benchmarks comparativos entre execuções sequenciais e paralelas.

## Tecnologias utilizadas

### Backend
- **FastAPI** - Framework web moderno e rápido
- **SQLAlchemy 2.0** - ORM assíncrono/síncrono
- **PostgreSQL 16** - Banco de dados relacional
- **PyOpenCL** - Computação paralela OpenCL
- **Pydantic/Pydantic Settings** - Validação e configuração
- **Passlib/Argon2** - Hash seguro de senhas
- **python-jose** - JWT tokens
- **pandas, NumPy, scikit-learn** - Processamento de dados e ML

### Frontend
- **Angular 22** - Framework SPA com signals e novo control-flow
- **RxJS 7** - Programação reativa
- **TypeScript 6** - Tipagem estática
- **Nginx** - Servidor web e proxy reverso

### Infraestrutura
- **Docker Compose** - Orquestração de containers
- **PostgreSQL 16 Alpine** - Imagem oficial do banco
- **Volumes persistentes** - Dados do banco e arquivos CSV

## Requisitos necessários para execução

### Com Docker (recomendado)
- Docker Desktop 4.x+
- Docker Compose 2.x+

### Execução local (sem Docker)
- Python 3.11+
- PostgreSQL 16+
- Node.js 22+ e npm
- Runtime OpenCL compatível (PoCL, NVIDIA CUDA, AMD ROCm, Intel OpenCL)

## Instruções de instalação e configuração

### 1. Clone o repositório
```bash
git clone <url-do-repositorio>
cd projeto-transacao
```

### 2. Configure variáveis de ambiente
```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

Edite o arquivo `.env` e ajuste pelo menos:
- `POSTGRES_PASSWORD` - Senha segura para o banco
- `JWT_SECRET_KEY` - Chave secreta forte para JWT (mín. 32 chars)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` - Expiração do token (padrão: 30)

### 3. Suba com Docker Compose
```powershell
docker compose up --build
```

Aguarde a inicialização completa (health checks do banco e backend).

### 4. Acesse o sistema
- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **Swagger/OpenAPI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Orientações para configurar o banco de dados

### Com Docker (automático)
O banco é criado automaticamente na primeira execução:
1. `database/schema.sql` - Cria tabelas, índices, constraints
2. `database/seeds.sql` - Dados iniciais (modelos de detecção)
3. Bootstrap da aplicação - Cria usuário admin padrão se tabela vazia

### Execução local (manual)
```powershell
# Criar banco e usuário
psql -U postgres -c "CREATE DATABASE fraud_detection;"
psql -U postgres -c "CREATE USER fraud WITH PASSWORD 'sua_senha';"
psql -U postgres -c "GRANT ALL PRIVILEGES ON DATABASE fraud_detection TO fraud;"

# Executar schema e seeds
Get-Content database/schema.sql | psql -U fraud -d fraud_detection
Get-Content database/seeds.sql | psql -U fraud -d fraud_detection
```

### Patches incrementais
Para bancos existentes, aplique patches sem apagar dados:
```powershell
Get-Content database/patches/work_group_size_limit.sql | docker compose exec -T db psql -U fraud -d fraud_detection
```

## Comandos para executar o sistema

### Docker Compose
```powershell
# Subir tudo (build + start)
docker compose up --build

# Subir em background
docker compose up -d --build

# Ver logs
docker compose logs -f backend
docker compose logs -f frontend

# Parar
docker compose down

# Parar e remover volumes (dados perdidos!)
docker compose down -v
```

### Backend local
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
$env:PYTHONPATH='backend'
# Configure DATABASE_URL no .env local
python -m uvicorn src.fraud_detector.main:app --reload --host 127.0.0.1 --port 8000
```

### Frontend local
```powershell
cd frontend
npm ci
npm run start:proxy  # usa proxy.conf.json para /api -> localhost:8000
```

### Testes e validação
```powershell
# Backend
python -m pytest tests
python -m ruff check backend tests
python -m compileall -q backend/src tests

# Frontend
cd frontend
npm run build -- --configuration production

# Docker
docker compose config
```

## Estrutura do projeto

```
projeto-transacao/
├── backend/
│   ├── src/fraud_detector/
│   │   ├── api/
│   │   │   ├── routes/          # Endpoints HTTP (auth, datasets, analyses, benchmarks)
│   │   │   ├── schemas/         # Pydantic models (request/response)
│   │   │   └── dependencies/    # Auth, roles, repositories
│   │   ├── application/         # Casos de uso (services)
│   │   ├── domain/              # Entidades, enums, regras de domínio
│   │   ├── computational/       # CSV streaming, pré-processamento, OpenCL
│   │   ├── infrastructure/      # DB, models SQLAlchemy, repositories, JWT/Argon2
│   │   └── config/              # Settings via Pydantic Settings
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/app/
│   │   ├── core/
│   │   │   ├── models/          # Interfaces TypeScript (Usuario, Dataset, etc.)
│   │   │   ├── services/        # AuthService, DatasetService, AnalysisService, BenchmarkService
│   │   │   ├── interceptors/    # authInterceptor (JWT + 401 handling)
│   │   │   └── guards/          # authGuard, roleGuard
│   │   ├── layout/shell/        # Sidebar fixa + router-outlet
│   │   ├── shared/components/   # StatCard, StatusBadge
│   │   └── features/            # Telas por domínio (lazy-loaded)
│   │       ├── auth/login
│   │       ├── dashboard
│   │       ├── datasets/
│   │       ├── analysis/
│   │       ├── benchmark/
│   │       └── history/
│   ├── proxy.conf.json
│   ├── nginx.conf
│   └── Dockerfile
├── database/
│   ├── schema.sql               # DDL completo
│   ├── seeds.sql                # Dados iniciais
│   └── patches/                 # Patches incrementais
├── docs/                        # Documentação técnica e sprints
├── docker-compose.yml
├── .env.example
└── README.md
```

## Documentação da API

A documentação interativa completa (Swagger/OpenAPI) está disponível em **http://localhost:8000/docs** quando o backend está rodando.

### Autenticação

Todos os endpoints de dados exigem **JWT Bearer Token** no header `Authorization`, exceto:
- `GET /` - Health check básico
- `GET /health` - Status detalhado
- `POST /auth/login` - Login
- `POST /auth/register` - Registro (apenas ADMIN)

**Perfis de acesso:**
- **ADMIN**: Todas as operações, incluindo cadastro de usuários
- **ANALISTA**: Leitura e operações de escrita (datasets, análises, benchmarks)
- **VISUALIZADOR**: Apenas leitura

### Endpoints Principais

#### Autenticação (`/auth`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| POST | `/auth/login` | Login com email/senha, retorna JWT | Não |
| POST | `/auth/register` | Cria usuário (apenas ADMIN) | ADMIN |
| GET | `/auth/me` | Perfil do usuário logado | JWT |
| PATCH | `/auth/me` | Atualiza nome, email ou senha | Escrita |
| DELETE | `/auth/users/{id_usuario}` | Exclui usuário (proteções) | ADMIN |

#### Transações (`/transactions`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| POST | `/transactions` | Cria transação | Escrita |
| GET | `/transactions` | Lista transações do usuário | JWT |
| GET | `/transactions/{id}` | Detalhe da transação | JWT |
| PATCH | `/transactions/{id}` | Atualiza campos | Escrita |
| DELETE | `/transactions/{id}` | Remove transação | Escrita |

#### Datasets (`/datasets`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| GET | `/datasets` | Lista datasets (com filtros/paginação) | JWT |
| GET | `/datasets/{id}` | Detalhes + amostra | JWT |
| POST | `/datasets/importacoes` | Cria job de importação | Escrita |
| POST | `/datasets/importacoes/{id}/arquivo` | Upload CSV (multipart) | Escrita |
| GET | `/datasets/importacoes/{id}` | Status do job | JWT |
| POST | `/datasets/importacoes/{id}/cancelar` | Cancela importação | Escrita |
| DELETE | `/datasets/{id}` | Remove dataset | Escrita |

#### Modelos (`/modelos`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| GET | `/modelos` | Lista modelos disponíveis | JWT |

#### Análises (`/analises`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| GET | `/analises/capacidades` | Dispositivos OpenCL detectados | JWT |
| POST | `/analises` | Cria execução (dataset, modelo, modo, device) | Escrita |
| GET | `/analises` | Histórico com filtros | JWT |
| GET | `/analises/{id}` | Detalhe da execução | JWT |
| DELETE | `/analises/{id}` | Remove execução | Escrita |
| POST | `/analises/{id}/cancelar` | Solicita cancelamento | Escrita |
| GET | `/analises/{id}/status` | Progresso (polling) | JWT |
| GET | `/analises/{id}/resultados` | Resultados paginados/filtrados | JWT |
| GET | `/analises/{id}/resultados/{transaction_id}` | Detalhe + histórico | JWT |

#### Benchmarks (`/benchmarks`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| GET | `/benchmarks/capacidades` | Dispositivos OpenCL | JWT |
| POST | `/benchmarks` | Cria benchmark comparativo | Escrita |
| GET | `/benchmarks/{id}` | Relatório com execuções | JWT |
| POST | `/benchmarks/{id}/cancelar` | Cancela benchmark | Escrita |


### Exemplos de uso

#### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@admin.com", "senha": "admin123"}'
```
Resposta:
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer"
}
```

#### Criar dataset (importação)
```bash
# 1. Criar job
curl -X POST http://localhost:8000/datasets/importacoes \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"nome": "Meu Dataset", "origem": "csv", "descricao": "Transações jan/2024"}'

# 2. Upload do arquivo (multipart)
curl -X POST http://localhost:8000/datasets/importacoes/{id}/arquivo \
  -H "Authorization: Bearer $TOKEN" \
  -F "arquivo=@transacoes.csv"
```

#### Executar análise
```bash
curl -X POST http://localhost:8000/analises \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dataset": 1,
    "id_modelo": 1,
    "modo_execucao": "PARALELO",
    "tipo_dispositivo": "GPU",
    "work_group_size": 256
  }'
```

#### Acompanhar progresso (polling)
```bash
curl -X GET http://localhost:8000/analises/{id}/status \
  -H "Authorization: Bearer $TOKEN"
```

#### Obter resultados
```bash
curl -X GET "http://localhost:8000/analises/{id}/resultados?pagina=1&tamanho_pagina=25&escore_minimo=0.7" \
  -H "Authorization: Bearer $TOKEN"
```

#### Exportar resultados
```bash
# PDF
curl -X GET "http://localhost:8000/analises/{id}/resultados/exportar?formato=pdf" \
  -H "Authorization: Bearer $TOKEN" \
  --output analise-{id}.pdf

# CSV
curl -X GET "http://localhost:8000/analises/{id}/resultados/exportar?formato=csv" \
  -H "Authorization: Bearer $TOKEN" \
  --output analise-{id}.csv
```

#### Benchmark
```bash
curl -X POST http://localhost:8000/benchmarks \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "id_dataset": 1,
    "id_modelo": 1,
    "configuracoes": [
      {"modo_execucao": "SEQUENCIAL", "work_group_size": 1, "rotulo": "Seq"},
      {"modo_execucao": "PARALELO", "work_group_size": 256, "rotulo": "Par 256"},
      {"modo_execucao": "PARALELO", "work_group_size": 512, "rotulo": "Par 512"}
    ]
  }'
```

## Usuário padrão (primeiro acesso)

Na primeira criação do banco, quando a tabela de usuários está vazia, a API cria o usuário inicial:

- **Email/login**: `admin@admin.com`
- **Senha**: `admin123`
- **Perfil**: administrador

**Importante**: 
1. Entre com o usuário padrão
2. Pela interface, crie um novo usuário com perfil administrador
3. Entre com esse novo usuário administrador
4. Exclua o usuário padrão

A senha padrão é pública e deve ser trocada ou removida após configurar outro administrador.

## Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `POSTGRES_USER` | `fraud` | Usuário PostgreSQL |
| `POSTGRES_PASSWORD` | `fraud` | Senha PostgreSQL (troque em produção!) |
| `POSTGRES_DB` | `fraud_detection` | Nome do banco |
| `POSTGRES_PORT` | `5432` | Porta do banco |
| `BACKEND_PORT` | `8000` | Porta da API |
| `FRONTEND_PORT` | `4200` | Porta do frontend |
| `JWT_SECRET_KEY` | segredo local | Chave JWT (mín. 32 chars em produção) |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Validade do token |
| `DATABASE_URL` | composta pelo Compose | URL SQLAlchemy |
| `DATASET_STORAGE_PATH` | `/app/storage/datasets` | Diretório CSVs |
| `MAX_DATASET_UPLOAD_BYTES` | `209715200` | Limite upload (200MB) |
| `DATASET_UPLOAD_CHUNK_BYTES` | `1048576` | Chunk size (1MB) |
| `INGESTION_COPY_BUFFER_BYTES` | `1048576` | Buffer COPY PostgreSQL |
| `INGESTION_PROGRESS_EVERY_ROWS` | `50000` | Frequência progresso |
| `CORS_ORIGINS` | origins locais | JSON array de origens CORS |

## Uso de GPU (OpenCL)

### No Docker
O backend usa **PoCL** (Portable Computing Language) e expõe apenas dispositivo **CPU OpenCL**. A GPU NVIDIA não é acessível via OpenCL no Docker Desktop/WSL2 atual.

### Para usar GPU NVIDIA
1. Suba apenas banco e frontend pelo Docker:
   ```powershell
   docker compose up -d db frontend
   ```
2. No Windows, execute o backend nativamente:
   ```powershell
   cd backend
   python -m venv .venv
   .\.venv\Scripts\activate
   python -m pip install -r requirements.txt
   # Configure .env local com DATABASE_URL=postgresql://fraud:senha@localhost:5432/fraud_detection
   python -m uvicorn src.fraud_detector.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
   ```
3. Inicie frontend localmente:
   ```powershell
   cd frontend
   npm run start:proxy
   ```

### Validação
```bash

python -c "import pyopencl as cl; print([(p.name, [d.name for d in p.get_devices()]) for p in cl.get_platforms()])"

# Docker (mostra PoCL/CPU apenas)
docker compose exec backend python -c "import pyopencl as cl; print([(p.name, [d.name for d in p.get_devices()]) for p in cl.get_platforms()])"
```

## Limitações conhecidas

- Jobs usam `BackgroundTasks`; reinício pode deixar job em estado não terminal
- Nginx localiza backend por nome de serviço Compose; fora do Compose usa `proxy.conf.json`
- OpenCL depende de runtime/drivers disponíveis
- Alguns endpoints retornam listas completas; paginação pode ser necessária em produção
- Seed contém credenciais de desenvolvimento (não usar em produção)

## Integrantes da equipe

| Nome |
|------|
| Bruno Severino de Almeida Rocha|
| Rodrigo Amorim Neves |
| Everson Padilha Ferreira |
| Eduardo Barros Magalhães |

---
