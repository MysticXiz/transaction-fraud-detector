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
- **SQLAlchemy 2.0** - ORM síncrono
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
- Node.js 24 e npm
- Runtime OpenCL compatível (PoCL, NVIDIA CUDA, AMD ROCm, Intel OpenCL)

## Instruções de instalação e configuração

### 1. Clone o repositório
```bash
git clone https://github.com/MysticXiz/transaction-fraud-detector.git
cd transaction-fraud-detector
```

### 2. Configure variáveis de ambiente
```powershell
# Windows PowerShell
Copy-Item .env.example .env
```

O `.env.example` contém valores fictícios para facilitar a demonstração local. Na sua instalação, personalize a senha do banco, a chave JWT e as credenciais do administrador no `.env`.

### 3. Suba com Docker Compose
```powershell
docker compose up --build --remove-orphans
```

Aguarde o PostgreSQL e o health check do backend. O backend verifica se as tabelas e colunas necessárias estão acessíveis e processa a fila em segundo plano. O Compose disponibiliza os serviços em `localhost`.

### 4. Acesse o sistema
- **Frontend**: http://localhost:4200
- **Backend API**: http://localhost:8000
- **Swagger/OpenAPI**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Orientações para configurar o banco de dados

### Com Docker
O PostgreSQL executa `database/schema.sql` e `database/seeds.sql` na primeira inicialização de um volume vazio. O Alembic é executado manualmente.

Em um volume existente, altere a senha do usuário no PostgreSQL antes de atualizar o valor de `POSTGRES_PASSWORD` no `.env`. A variável do contêiner é aplicada na criação do volume.

### Execução local
Crie um banco PostgreSQL vazio com o usuário da aplicação como proprietário. O backend monta a URL com `DATABASE_HOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD` e `POSTGRES_DB`. Para fornecer a URL completa, configure `DATABASE_URL` no formato `postgresql+psycopg://usuario:senha@localhost:5432/banco`. Para inicializar pelo fluxo SQL, execute os comandos abaixo.

```powershell
psql -h localhost -U fraud -d fraud_detection -v ON_ERROR_STOP=1 -f database/schema.sql
psql -h localhost -U fraud -d fraud_detection -v ON_ERROR_STOP=1 -f database/seeds.sql
```

### Alembic (execução manual)

A revisão `0001_initial_schema` cria o esquema completo e cadastra os modelos iniciais. Ela usa cópias SQL fixas em `database/migrations/versions/`; os scripts de inicialização do Compose são independentes. Registre alterações futuras em novas revisões.

Para gerar o SQL sem conexão com o banco, execute `python -m alembic upgrade head --sql` na raiz do repositório.

Ao adotar o Alembic, execute `python -m alembic upgrade head` em um PostgreSQL vazio. Se você já recriou o banco com os scripts SQL desta versão, registre a revisão correspondente com `python -m alembic stamp 0001_initial_schema` depois de confirmar que o esquema corresponde a ela. Para aplicar revisões posteriores, use `python -m alembic upgrade head`. No Docker, comandos para um banco já inicializado podem ser executados no contêiner do backend com o prefixo `docker compose exec backend`.

## Comandos para executar o sistema

### Docker Compose
```powershell
# Subir tudo (build + start)
docker compose up --build --remove-orphans

# Subir em background
docker compose up -d --build --remove-orphans

# Ver logs
docker compose logs -f backend
docker compose logs -f frontend

# Parar
docker compose down

```

### Backend local
Execute na raiz do repositório.

```powershell
python -m venv backend/.venv
.\backend\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:PYTHONPATH='backend'
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
│   └── migrations/              # Revisões do Alembic
├── alembic.ini
├── docker-compose.yml
├── .env.example
└── README.md
```

## Documentação da API

A documentação interativa completa (Swagger/OpenAPI) está disponível em **http://localhost:8000/docs** quando o backend está rodando.

### Autenticação

Os endpoints protegidos aceitam JWT Bearer no cabeçalho `Authorization`. O Angular usa uma sessão por cookie `HttpOnly` e `SameSite=Lax` com o cabeçalho `X-Requested-With: XMLHttpRequest` nas operações de escrita.

**Perfis de acesso:**
- **ADMIN**: Todas as operações, incluindo cadastro de usuários
- **ANALISTA**: Leitura e operações de escrita (datasets, análises, benchmarks)
- **VISUALIZADOR**: Apenas leitura

### Endpoints Principais

#### Autenticação (`/auth`)
| Método | Rota | Descrição | Auth |
|--------|------|-----------|------|
| POST | `/auth/login` | Login de clientes da API, retorna JWT | Pública |
| POST | `/auth/session` | Abre sessão por cookie | Cabeçalho de sessão |
| POST | `/auth/logout` | Limpa o cookie da sessão | Cabeçalho de sessão |
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
| GET | `/analises/{id}` | Detalhe e progresso da execução | JWT |
| DELETE | `/analises/{id}` | Remove execução | Escrita |
| POST | `/analises/{id}/cancelar` | Solicita cancelamento | Escrita |
| GET | `/analises/{id}/resultados` | Resultados paginados e filtrados | JWT |
| GET | `/analises/{id}/resultados/exportar` | CSV ou JSON de uma análise concluída | JWT |
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
  -d '{"email": "administrador@exemplo.com", "senha": "<senha-configurada>"}'
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
curl -X GET http://localhost:8000/analises/{id} \
  -H "Authorization: Bearer $TOKEN"
```

#### Obter resultados
```bash
curl -X GET "http://localhost:8000/analises/{id}/resultados?pagina=1&tamanho_pagina=25&escore_minimo=0.7&is_suspeita=true" \
  -H "Authorization: Bearer $TOKEN"
```

#### Exportar resultados

CSV e JSON usam os mesmos filtros opcionais da tabela, incluindo `is_suspeita`, e incluem todas as linhas que correspondem aos filtros. O download lê os resultados persistidos em lotes e envia o arquivo progressivamente. A sessão da exportação ocupa uma conexão PostgreSQL durante o download.

O JSON contém um array com uma transação por linha. Em arquivos grandes, filtre os resultados antes de exportar ou use `Get-Content .\analise-123.json -TotalCount 6` no PowerShell para ver as primeiras linhas.

```bash
curl -f "http://localhost:8000/analises/{id}/resultados/exportar?formato=csv&is_suspeita=true" \
  -H "Authorization: Bearer $TOKEN" \
  --output analise-{id}.csv

curl -f "http://localhost:8000/analises/{id}/resultados/exportar?formato=json" \
  -H "Authorization: Bearer $TOKEN" \
  --output analise-{id}.json
```

#### Benchmark

Em novas análises paralelas comuns, a tela de resultados soma os tempos registrados pelo dispositivo OpenCL por lote, incluindo cópia de entrada, kernel e cópia de saída. O tempo restante é a diferença em relação ao tempo total após descontar leitura, pré-processamento e inferência. A gravação pode ocorrer junto com o OpenCL, então essa diferença não mede toda a escrita no banco. Para ver o tempo de treinamento e a espera pela gravação final, consulte os logs do backend.

O speedup de inferência divide o tempo sequencial pelo tempo da configuração comparada. Para cada configuração, o benchmark aquece o primeiro lote e soma o tempo necessário para produzir os scores de todos os lotes. No OpenCL, cada medição começa antes de enviar o lote e termina quando os scores retornam, incluindo as transferências. Uma falha do OpenCL interrompe a comparação.

O treinamento usa uma thread no modo sequencial e a capacidade de CPU detectada no modo paralelo. Os logs do backend mostram o dispositivo OpenCL, as unidades de computação e a ocupação média do processo durante as fases de treinamento e inferência. A ocupação durante a inferência inclui as threads de gravação que estiverem ativas nessa fase.

O tempo total inclui leitura, pré-processamento, ajuste do modelo, aquecimento e gravação dos resultados. Benchmarks antigos com execução paralela usam a medição anterior e precisam ser executados novamente para obter o speedup pelo método atual.
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

## Primeiro acesso

Em um banco sem usuários, a API cria o administrador com os valores de `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD`. Em um banco com a conta padrão antiga ainda usando a senha pública, as mesmas variáveis atualizam essa conta, preservando seu ID e seus dados.

### Configurações do servidor

O administrador pode acessar **Dashboard → Configurações do servidor** para alterar o limite global de upload e criar ou gerenciar contas. O limite varia de 1 a 10.240 MiB por CSV, entra em vigor nos próximos uploads e fica salvo no volume de datasets. `MAX_DATASET_UPLOAD_BYTES` fornece o valor inicial até a primeira alteração pelo painel.

## Variáveis de ambiente

| Variável | Default | Descrição |
|----------|---------|-----------|
| `POSTGRES_USER` | `fraud` | Usuário PostgreSQL |
| `POSTGRES_PASSWORD` | Obrigatória no Compose | Senha PostgreSQL |
| `POSTGRES_DB` | `fraud_detection` | Nome do banco |
| `POSTGRES_PORT` | `5432` | Porta do banco |
| `BACKEND_PORT` | `8000` | Porta da API |
| `FRONTEND_PORT` | `4200` | Porta do frontend |
| `JWT_SECRET_KEY` | Obrigatória | Chave JWT com pelo menos 32 caracteres |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Validade do token |
| `DATABASE_HOST` | `127.0.0.1` no exemplo, `db` no Compose | Host do PostgreSQL |
| `DATABASE_URL` | Opcional | URL SQLAlchemy que substitui host e credenciais na execução local |
| `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` | Opcionais | Criação ou atualização da conta inicial |
| `AUTH_COOKIE_SECURE` | `false` | Defina `true` para HTTPS |
| `DATASET_STORAGE_PATH` | `/app/storage/datasets` | Diretório CSVs |
| `MAX_DATASET_UPLOAD_BYTES` | `209715200` | Limite inicial de upload (200 MiB) |
| `DATASET_UPLOAD_MULTIPART_OVERHEAD_BYTES` | `4194304` | Margem para o corpo multipart além do limite do CSV (4 MiB) |
| `ANALYSIS_MATRIX_MEMORY_LIMIT_BYTES` | `536870912` | Orçamento estimado para a matriz da análise (512 MiB; não limita toda a memória do processo) |
| `DATASET_UPLOAD_CHUNK_BYTES` | `1048576` | Chunk size (1MB) |
| `INGESTION_COPY_BUFFER_BYTES` | `1048576` | Buffer COPY PostgreSQL |
| `INGESTION_PROGRESS_EVERY_ROWS` | `50000` | Frequência progresso |
| `CORS_ORIGINS` | origins locais | JSON array de origens CORS |

Para testar cerca de 1 milhão de linhas com 28 atributos numéricos, use `ANALYSIS_MATRIX_MEMORY_LIMIT_BYTES=2147483648` no `.env`, se houver memória disponível. Recrie apenas o backend para aplicar a configuração.

## Uso de GPU (OpenCL)

### No Docker
O backend usa **PoCL** (Portable Computing Language) e expõe apenas dispositivo **CPU OpenCL**. O runtime detecta os recursos de CPU disponíveis no ambiente, sem um limite de núcleos definido pelo projeto. A GPU NVIDIA não é acessível via OpenCL no Docker Desktop/WSL2 atual.

### Para usar GPU NVIDIA
Suba o PostgreSQL com `docker compose up -d db`. Execute o backend e o frontend no host conforme as instruções de execução local. O ambiente Python do backend precisa enxergar a GPU pelo runtime OpenCL.

### Validação
```bash

python -c "import pyopencl as cl; print([(p.name, [d.name for d in p.get_devices()]) for p in cl.get_platforms()])"

# Docker (mostra PoCL/CPU apenas)
docker compose exec backend python -c "import pyopencl as cl; print([(p.name, [d.name for d in p.get_devices()]) for p in cl.get_platforms()])"
```

## Limitações conhecidas

- Análises e benchmarks pendentes ficam no PostgreSQL e continuam disponíveis após reinício. O backend marca execuções interrompidas como falha para que possam ser iniciadas novamente.
- A leitura e a inferência trabalham em blocos. O ajuste ainda mantém a matriz numérica em memória; a execução rejeita uma matriz cuja estimativa exceda o orçamento configurado.
- Transações de datasets vinculados a análises ou benchmarks não podem ser editadas; importe outra versão dos dados para preservar os resultados históricos.
- Jobs de importação interrompidos são reconciliados quando consultados ou cancelados; a transferência não é retomada automaticamente.
- Nginx localiza backend por nome de serviço Compose; fora do Compose usa `proxy.conf.json`
- OpenCL depende de runtime/drivers disponíveis
- Alguns endpoints retornam listas completas; paginação pode ser necessária para bases maiores
- Isolation Forest é o único detector executável. A entrada de Regressão Logística no seed é uma referência histórica.

## Documentação da entrega

- [Manual do Usuário](docs/01-manual-do-usuario.docx)
- [Manual Técnico](docs/02-manual-tecnico.docx)
- [Relatório consolidado da entrega](docs/sprint11.pdf)

## Integrantes da equipe

| Nome |
|------|
| Bruno Severino de Almeida Rocha|
| Rodrigo Amorim Neves |
| Everson Padilha Ferreira |
| Eduardo Barros Magalhães |

---
