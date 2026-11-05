# Detector de Fraudes em Transações

## Visão geral

Sistema full-stack para importação de datasets, detecção de transações suspeitas, acompanhamento de análises e execução de benchmarks com OpenCL.

- Backend: FastAPI, SQLAlchemy 2, PostgreSQL e PyOpenCL
- Frontend: Angular 22, RxJS e TypeScript
- Banco: PostgreSQL 16
- Infraestrutura: Docker Compose, Nginx e volumes persistentes

## Funcionalidades

- Login com JWT e perfis ADMIN, ANALISTA e VISUALIZADOR
- Importação de arquivos CSV com validação, hash SHA-256 e acompanhamento de progresso
- CRUD de transações pertencentes ao usuário
- Análises com isolamento forest, OpenCL e exportação de resultados
- Benchmarks sequenciais e paralelos
- Histórico e cancelamento de execuções

## Estrutura

```text
backend/src/fraud_detector/  API, casos de uso, domínio e infraestrutura
frontend/src/app/             Frontend Angular
frontend/src/environments/    Configuração de ambiente
frontend/src/app/features/    Telas por domínio
frontend/src/app/core/        Guards, serviços, interceptors e modelos
database/                     Schema SQL e seed inicial
tests/                        Testes unitários e de desempenho
```

## Pré-requisitos

- Docker Desktop e Docker Compose, ou
- Python 3.11+, PostgreSQL 16, Node.js 22+ e npm
- Um runtime OpenCL compatível para benchmark/análise GPU ou CPU OpenCL

## Subir com Docker

1. Copie o arquivo de exemplo:

```powershell
Copy-Item .env.example .env
```

2. Ajuste pelo menos `POSTGRES_PASSWORD` e `JWT_SECRET_KEY`, depois execute:

```powershell
docker compose up --build
```

3. Acesse:

- Frontend: http://localhost:4200
- Backend e Swagger: http://localhost:8000/docs
- Health check: http://localhost:8000/health

A instalação nova cria o banco com `database/schema.sql`, executa `database/seeds.sql` e inicia o bootstrap do usuário padrão pela aplicação.

## Usuário padrão (primeiro acesso)

Na primeira criação do banco, quando a tabela de usuários está vazia, a API cria o usuário inicial:

- Email/login: `admin@admin.com`
- Senha: `admin123`
- Perfil: administrador

1. Entre com o usuário padrão.
2. Pela interface, crie um novo usuário com perfil administrador.
3. Entre com esse novo usuário administrador.
4. Exclua o usuário padrão.

A senha padrão é pública e deve ser trocada ou removida após configurar outro administrador. Para recriar o usuário padrão do zero, é necessário executar `docker compose down -v`; isso apaga todos os dados persistidos. O sistema impede excluir o último administrador ativo e a própria conta enquanto o usuário está logado.

Para encerrar:

```powershell
docker compose down
```

Para remover também os dados locais:

```powershell
docker compose down -v
```

## Executar localmente

### Banco

```powershell
Get-Content database/schema.sql | docker exec -i fraud_db psql -U fraud -d fraud_detection
Get-Content database/seeds.sql | docker exec -i fraud_db psql -U fraud -d fraud_detection
```

Com PostgreSQL já instalado, crie o banco e execute os mesmos arquivos pelo `psql`.

### Backend

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
$env:PYTHONPATH='backend'
python -m uvicorn src.fraud_detector.main:app --reload --host 127.0.0.1 --port 8000
```

Configure `DATABASE_URL` no `.env` para apontar ao PostgreSQL local. A API fica em http://localhost:8000 e `/docs` abre o Swagger.

### Frontend

```powershell
cd frontend
npm ci
npm run start:proxy
```

O frontend fica em http://localhost:4200. `proxy.conf.json` encaminha `/api` para http://127.0.0.1:8000.

## Variáveis de ambiente

| Variável | Default Docker/local | Uso |
|---|---|---|
| `POSTGRES_USER` | `fraud` | Usuário administrativo do PostgreSQL |
| `POSTGRES_PASSWORD` | `fraud` | Senha do PostgreSQL; substitua fora de desenvolvimento |
| `POSTGRES_DB` | `fraud_detection` | Banco da aplicação |
| `POSTGRES_PORT` | `5432` | Porta publicada do PostgreSQL |
| `BACKEND_PORT` | `8000` | Porta publicada da API |
| `FRONTEND_PORT` | `4200` | Porta publicada do frontend |
| `JWT_SECRET_KEY` | segredo local | Assinatura dos tokens JWT |
| `JWT_ALGORITHM` | `HS256` | Algoritmo JWT |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | Validade do token |
| `DATABASE_URL` | composto pelo Compose | URL SQLAlchemy do backend |
| `DATASET_STORAGE_PATH` | `/app/storage/datasets` | Diretório persistente dos CSVs |
| `MAX_DATASET_UPLOAD_BYTES` | `209715200` | Limite de upload |
| `DATASET_UPLOAD_CHUNK_BYTES` | `1048576` | Tamanho dos chunks enviados pelo cliente |
| `INGESTION_COPY_BUFFER_BYTES` | `1048576` | Buffer da carga PostgreSQL COPY |
| `INGESTION_PROGRESS_EVERY_ROWS` | `50000` | Frequência de atualização do progresso |
| `CORS_ORIGINS` | origins locais | Lista JSON das origens permitidas pelo CORS |

## Banco e migrations

Novas instalações usam `database/schema.sql` e `database/seeds.sql`. O projeto não usa migrations Alembic no fluxo atual: o Compose cria a base do zero na primeira inicialização e a aplicação executa apenas o seed idempotente do usuário bootstrap. Bancos existentes não são alterados automaticamente.

## API

A documentação interativa completa está em `/docs`.

Principais grupos:

| Método | Rota | Função |
|---|---|---|
| POST | `/auth/login` | Login |
| GET/PATCH | `/auth/me` | Perfil atual |
| POST | `/auth/register` | Cadastro administrativo |
| DELETE | `/auth/users/{id_usuario}` | Exclusão administrativa com proteções |
| GET/POST/PATCH/DELETE | `/transactions` | CRUD de transações |
| POST/GET/DELETE | `/datasets` e `/datasets/{id}` | Dataset e exclusão |
| POST/GET | `/datasets/importacoes/...` | Job, upload, status e cancelamento de importação |
| GET/POST/DELETE | `/analises` | Configuração, histórico, cancelamento e resultados |
| POST/GET | `/benchmarks` | Execução e relatório |
| GET | `/modelos` | Modelos disponíveis |

## Testes e validação

```powershell
python -m pytest tests
python -m ruff check backend tests
python -m compileall -q backend/src tests
cd frontend
npm run build -- --configuration production
docker compose config
```

## Uso de GPU (OpenCL)

No Docker, o backend usa PoCL e expõe apenas um dispositivo de CPU OpenCL. A GPU NVIDIA é opcional e pode ser usada executando o backend diretamente no Windows. CUDA e OpenCL NVIDIA são implementações diferentes; `nvidia-smi` e `gpus: all` podem confirmar acesso ao driver CUDA sem garantir que o PyOpenCL encontrará um ICD OpenCL NVIDIA. Por isso, o Compose não usa GPU passthrough. A documentação oficial do Docker confirma GPU-PV/CUDA no Desktop para Windows, mas não comprova OpenCL NVIDIA; [Docker Desktop GPU support](https://docs.docker.com/desktop/features/gpu/) e o [NVIDIA CUDA on WSL guide](https://docs.nvidia.com/cuda/wsl-user-guide/) não apresentam essa implementação como suportada pelo fluxo deste projeto.

Para usar a GTX 1660 SUPER:

1. Suba o banco e o frontend pelo Docker: `docker compose up -d db frontend`.
2. No Windows, crie o ambiente do backend: `cd backend`, `python -m venv .venv` e `.venv\Scripts\activate`.
3. Instale as dependências: `python -m pip install -r requirements.txt`.
4. Configure um `.env` na raiz usando `backend/.env.example.local` como referência. Aponte `DATABASE_URL` para `postgresql+psycopg://fraud:fraud@localhost:5432/fraud_detection`.
5. Inicie o backend: `python -m uvicorn src.fraud_detector.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000`.
6. Inicie também o frontend Angular localmente com `npm run start:proxy`; ele encaminha `/api` para `http://localhost:8000`.

Validação:

- Windows: `python -c "import pyopencl as cl; print([(p.name, [d.name for d in p.get_devices()]) for p in cl.get_platforms()])"` deve mostrar `NVIDIA CUDA` e a GTX 1660 SUPER.
- Docker: `docker compose exec backend python -c "import pyopencl as cl; print([(p.name, [d.name for d in p.get_devices()]) for p in cl.get_platforms()])"` deve mostrar PoCL/CPU e nenhuma GPU.
- `/api/analises/capacidades` deve listar apenas os dispositivos detectados pelo backend. "Tamanho máximo do work-group OpenCL" é um limite de execução do kernel, não quantidade de núcleos ou workers.

Se nenhum dispositivo OpenCL estiver disponível, a API informa uma lista vazia ou usa CPU sequencial conforme o padrão da execução; nenhuma GPU fictícia é anunciada.

## Solução de problemas

- **Backend não conecta ao banco no Docker:** aguarde o health check do PostgreSQL e confirme usuário, senha e nome do banco.
- **Frontend não encontra a API:** no Docker, `/api` é proxy do Nginx para `backend:8000`; localmente, execute com `npm run start:proxy`.
- **Token inválido:** confirme `JWT_SECRET_KEY` igual em todas as instâncias do backend e faça login novamente.
- **Upload falha:** confira `.csv`, limite configurado e espaço no volume `dataset-storage`.
- **CPU não aparece:** no Docker, a imagem inclui PoCL, que oferece um dispositivo OpenCL de CPU sem exigir um driver OpenCL nativo do processador. Reconstrua a imagem com `docker compose up -d --build backend`. O valor mostrado como máximo é o limite do work-group OpenCL, não a quantidade de núcleos ou workers da CPU/GPU.
- **GPU não aparece no Docker:** neste computador, o host detecta corretamente `NVIDIA GeForce GTX 1660 SUPER` pelo OpenCL, mas o container Linux não recebe o ICD/implementação OpenCL da NVIDIA. O Docker Desktop expõe CUDA/NVIDIA, porém isso não substitui o runtime OpenCL necessário pelo PyOpenCL. Para usar GPU nesta máquina, execute o backend localmente no Windows, como descrito na seção “Executar localmente”.
- **Teste dos dispositivos OpenCL:** execute `docker compose exec backend python -c "import pyopencl as cl; [print(p.name, p.get_devices()) for p in cl.get_platforms()]"`.
- **Banco já existente desatualizado:** recrie o banco do zero com `docker compose down -v` antes de usar uma instalação nova, pois esta versão não executa migrations automaticamente. Isso apaga os dados locais.
