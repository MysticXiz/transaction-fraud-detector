-- =====================================================================
-- SISTEMA INTELIGENTE DE DETECCAO DE FRAUDES EM TRANSACOES
-- Script de criacao do banco de dados - Sprint 02
-- SGBD: PostgreSQL 16
-- Equipe: Bruno S. A. Rocha / Rodrigo A. Neves / Everson P. Ferreira
-- =====================================================================

-- ---------------------------------------------------------------------
-- 0. LIMPEZA (ambiente de desenvolvimento)
-- ---------------------------------------------------------------------
DROP VIEW  IF EXISTS vw_comparativo_benchmark CASCADE;
DROP VIEW  IF EXISTS vw_resumo_execucao       CASCADE;

DROP TABLE IF EXISTS log_evento           CASCADE;
DROP TABLE IF EXISTS benchmark_execucao    CASCADE;
DROP TABLE IF EXISTS benchmark             CASCADE;
DROP TABLE IF EXISTS metrica_execucao      CASCADE;
DROP TABLE IF EXISTS resultado_deteccao    CASCADE;
DROP TABLE IF EXISTS execucao_analise      CASCADE;
DROP TABLE IF EXISTS modelo_deteccao       CASCADE;
DROP TABLE IF EXISTS transacao             CASCADE;
DROP TABLE IF EXISTS dataset               CASCADE;
DROP TABLE IF EXISTS usuario               CASCADE;

DROP TYPE  IF EXISTS nivel_log       CASCADE;
DROP TYPE  IF EXISTS papel_benchmark CASCADE;
DROP TYPE  IF EXISTS tipo_algoritmo  CASCADE;
DROP TYPE  IF EXISTS status_execucao CASCADE;
DROP TYPE  IF EXISTS modo_execucao   CASCADE;
DROP TYPE  IF EXISTS papel_usuario   CASCADE;

-- ---------------------------------------------------------------------
-- 1. TIPOS ENUMERADOS
-- ---------------------------------------------------------------------
CREATE TYPE papel_usuario   AS ENUM ('ADMIN', 'ANALISTA', 'VISUALIZADOR');
CREATE TYPE modo_execucao   AS ENUM ('SEQUENCIAL', 'PARALELO');
CREATE TYPE status_execucao AS ENUM ('PENDENTE', 'EM_ANDAMENTO', 'CONCLUIDA', 'FALHA', 'CANCELADA');
CREATE TYPE tipo_algoritmo  AS ENUM ('ISOLATION_FOREST', 'LOGISTIC_REGRESSION', 'XGBOOST', 'AUTOENCODER');
CREATE TYPE papel_benchmark AS ENUM ('BASELINE', 'COMPARACAO');
CREATE TYPE nivel_log       AS ENUM ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL');

-- ---------------------------------------------------------------------
-- 2. USUARIO
-- ---------------------------------------------------------------------
CREATE TABLE usuario (
    id_usuario   SERIAL        PRIMARY KEY,
    nome         VARCHAR(120)  NOT NULL,
    email        VARCHAR(160)  NOT NULL,
    senha_hash   VARCHAR(255)  NOT NULL,
    papel        papel_usuario NOT NULL DEFAULT 'ANALISTA',
    ativo        BOOLEAN       NOT NULL DEFAULT TRUE,
    criado_em    TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_usuario_email   UNIQUE (email),
    CONSTRAINT ck_usuario_email   CHECK (email LIKE '%@%.%')
);

COMMENT ON TABLE usuario IS 'Analistas e administradores que operam o sistema (UC01, UC02, UC06).';

-- ---------------------------------------------------------------------
-- 3. DATASET
-- ---------------------------------------------------------------------
CREATE TABLE dataset (
    id_dataset      SERIAL       PRIMARY KEY,
    id_usuario      INTEGER      NOT NULL,
    nome            VARCHAR(160) NOT NULL,
    descricao       TEXT,
    caminho_arquivo VARCHAR(500) NOT NULL,
    hash_arquivo    CHAR(64)     NOT NULL,
    total_registros INTEGER      NOT NULL DEFAULT 0,
    total_colunas   SMALLINT     NOT NULL,
    origem          VARCHAR(80),
    possui_rotulo   BOOLEAN      NOT NULL DEFAULT FALSE,
    importado_em    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_dataset_usuario     FOREIGN KEY (id_usuario)
        REFERENCES usuario (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT uk_dataset_hash        UNIQUE (hash_arquivo),
    CONSTRAINT ck_dataset_registros   CHECK (total_registros >= 0),
    CONSTRAINT ck_dataset_colunas     CHECK (total_colunas > 0)
);

COMMENT ON COLUMN dataset.hash_arquivo IS
    'SHA-256 do arquivo importado. Impede reimportacao duplicada e garante que benchmarks comparem execucoes sobre dados identicos.';

-- ---------------------------------------------------------------------
-- 4. TRANSACAO
-- ---------------------------------------------------------------------
CREATE TABLE transacao (
    id_transacao   BIGSERIAL     PRIMARY KEY,
    id_dataset     INTEGER       NOT NULL,
    indice_origem  INTEGER       NOT NULL,
    valor          NUMERIC(14,2),
    tempo_relativo NUMERIC(14,4),
    atributos      JSONB         NOT NULL DEFAULT '{}'::jsonb,
    rotulo_real    BOOLEAN,
    CONSTRAINT fk_transacao_dataset FOREIGN KEY (id_dataset)
        REFERENCES dataset (id_dataset) ON DELETE CASCADE,
    CONSTRAINT uk_transacao_origem  UNIQUE (id_dataset, indice_origem),
    CONSTRAINT ck_transacao_indice  CHECK (indice_origem >= 0)
);

COMMENT ON COLUMN transacao.atributos IS
    'Features heterogeneas definidas em tempo de execucao pelo arquivo importado (ex.: V1..V28 da base ULB).';
COMMENT ON COLUMN transacao.rotulo_real IS
    'Rotulo verdadeiro, quando a base possui gabarito. NULL em bases nao rotuladas.';

-- ---------------------------------------------------------------------
-- 5. MODELO_DETECCAO
-- ---------------------------------------------------------------------
CREATE TABLE modelo_deteccao (
    id_modelo        SERIAL        PRIMARY KEY,
    nome             VARCHAR(120)  NOT NULL,
    algoritmo        tipo_algoritmo NOT NULL,
    versao           VARCHAR(20)   NOT NULL DEFAULT '1.0.0',
    hiperparametros  JSONB         NOT NULL DEFAULT '{}'::jsonb,
    caminho_artefato VARCHAR(500),
    limiar_padrao    NUMERIC(6,4)  NOT NULL DEFAULT 0.5000,
    metricas_treino  JSONB,
    treinado_em      TIMESTAMPTZ,
    criado_em        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    CONSTRAINT uk_modelo_nome_versao UNIQUE (nome, versao),
    CONSTRAINT ck_modelo_limiar      CHECK (limiar_padrao BETWEEN 0 AND 1)
);

-- ---------------------------------------------------------------------
-- 6. EXECUCAO_ANALISE
-- ---------------------------------------------------------------------
CREATE TABLE execucao_analise (
    id_execucao      SERIAL          PRIMARY KEY,
    id_dataset       INTEGER         NOT NULL,
    id_modelo        INTEGER         NOT NULL,
    id_usuario       INTEGER         NOT NULL,
    modo_execucao    modo_execucao   NOT NULL,
    num_workers      SMALLINT        NOT NULL DEFAULT 1,
    tamanho_chunk    INTEGER,
    limiar_aplicado  NUMERIC(6,4)    NOT NULL DEFAULT 0.5000,
    status           status_execucao NOT NULL DEFAULT 'PENDENTE',
    iniciada_em      TIMESTAMPTZ,
    finalizada_em    TIMESTAMPTZ,
    tempo_total_s    NUMERIC(12,6),
    total_analisadas INTEGER         NOT NULL DEFAULT 0,
    total_suspeitas  INTEGER         NOT NULL DEFAULT 0,
    mensagem_erro    TEXT,
    criado_em        TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_execucao_dataset FOREIGN KEY (id_dataset)
        REFERENCES dataset (id_dataset) ON DELETE RESTRICT,
    CONSTRAINT fk_execucao_modelo  FOREIGN KEY (id_modelo)
        REFERENCES modelo_deteccao (id_modelo) ON DELETE RESTRICT,
    CONSTRAINT fk_execucao_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuario (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT ck_execucao_workers CHECK (num_workers BETWEEN 1 AND 128),
    CONSTRAINT ck_execucao_chunk   CHECK (tamanho_chunk IS NULL OR tamanho_chunk > 0),
    CONSTRAINT ck_execucao_tempos  CHECK (finalizada_em IS NULL OR iniciada_em IS NULL
                                          OR finalizada_em >= iniciada_em),
    CONSTRAINT ck_execucao_totais  CHECK (total_suspeitas <= total_analisadas),
    -- Coerencia semantica: execucao sequencial obrigatoriamente usa 1 processo
    CONSTRAINT ck_execucao_modo_workers CHECK (
        modo_execucao <> 'SEQUENCIAL' OR num_workers = 1
    )
);

COMMENT ON TABLE execucao_analise IS
    'Cada linha representa um processamento completo de um dataset (RF05, RF09, UC02, UC03).';

-- ---------------------------------------------------------------------
-- 7. RESULTADO_DETECCAO
-- ---------------------------------------------------------------------
CREATE TABLE resultado_deteccao (
    id_resultado    BIGSERIAL     PRIMARY KEY,
    id_execucao     INTEGER       NOT NULL,
    id_transacao    BIGINT        NOT NULL,
    score_anomalia  NUMERIC(10,6) NOT NULL,
    is_suspeita     BOOLEAN       NOT NULL,
    limiar_aplicado NUMERIC(6,4)  NOT NULL,
    chunk_id        INTEGER,
    CONSTRAINT fk_resultado_execucao  FOREIGN KEY (id_execucao)
        REFERENCES execucao_analise (id_execucao) ON DELETE CASCADE,
    CONSTRAINT fk_resultado_transacao FOREIGN KEY (id_transacao)
        REFERENCES transacao (id_transacao) ON DELETE CASCADE,
    CONSTRAINT uk_resultado_exec_trans UNIQUE (id_execucao, id_transacao),
    CONSTRAINT ck_resultado_chunk      CHECK (chunk_id IS NULL OR chunk_id >= 0)
);

COMMENT ON TABLE resultado_deteccao IS
    'Entidade associativa que resolve o N:N entre TRANSACAO e EXECUCAO_ANALISE. Permite reavaliar a mesma transacao em modos sequencial e paralelo e comparar os resultados (RNF de Paralelizacao).';
COMMENT ON COLUMN resultado_deteccao.chunk_id IS
    'Bloco de processamento que gerou o resultado. Permite rastrear falhas ate o worker de origem.';

-- ---------------------------------------------------------------------
-- 8. METRICA_EXECUCAO (relacao 1:1 com execucao_analise)
-- ---------------------------------------------------------------------
CREATE TABLE metrica_execucao (
    id_metrica          SERIAL        PRIMARY KEY,
    id_execucao         INTEGER       NOT NULL,
    tempo_leitura_s     NUMERIC(12,6),
    tempo_preproc_s     NUMERIC(12,6),
    tempo_inferencia_s  NUMERIC(12,6),
    tempo_overhead_s    NUMERIC(12,6),
    cpu_percent_medio   NUMERIC(5,2),
    memoria_pico_mb     NUMERIC(10,2),
    throughput_tps      NUMERIC(12,2),
    nucleos_disponiveis SMALLINT,
    CONSTRAINT fk_metrica_execucao FOREIGN KEY (id_execucao)
        REFERENCES execucao_analise (id_execucao) ON DELETE CASCADE,
    CONSTRAINT uk_metrica_execucao UNIQUE (id_execucao),
    CONSTRAINT ck_metrica_cpu      CHECK (cpu_percent_medio IS NULL
                                          OR cpu_percent_medio BETWEEN 0 AND 100)
);

COMMENT ON COLUMN metrica_execucao.tempo_overhead_s IS
    'Custo atribuivel a criacao de processos, serializacao e comunicacao interprocessos. Zero no modo sequencial.';

-- ---------------------------------------------------------------------
-- 9. BENCHMARK
-- ---------------------------------------------------------------------
CREATE TABLE benchmark (
    id_benchmark SERIAL       PRIMARY KEY,
    id_usuario   INTEGER      NOT NULL,
    id_dataset   INTEGER      NOT NULL,
    descricao    VARCHAR(255),
    criado_em    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_benchmark_usuario FOREIGN KEY (id_usuario)
        REFERENCES usuario (id_usuario) ON DELETE RESTRICT,
    CONSTRAINT fk_benchmark_dataset FOREIGN KEY (id_dataset)
        REFERENCES dataset (id_dataset) ON DELETE CASCADE
);

CREATE TABLE benchmark_execucao (
    id_benchmark_exec SERIAL          PRIMARY KEY,
    id_benchmark      INTEGER         NOT NULL,
    id_execucao       INTEGER         NOT NULL,
    papel             papel_benchmark NOT NULL,
    speedup           NUMERIC(8,4),
    eficiencia        NUMERIC(6,4),
    CONSTRAINT fk_bexec_benchmark FOREIGN KEY (id_benchmark)
        REFERENCES benchmark (id_benchmark) ON DELETE CASCADE,
    CONSTRAINT fk_bexec_execucao  FOREIGN KEY (id_execucao)
        REFERENCES execucao_analise (id_execucao) ON DELETE CASCADE,
    CONSTRAINT uk_bexec           UNIQUE (id_benchmark, id_execucao),
    CONSTRAINT ck_bexec_speedup   CHECK (speedup    IS NULL OR speedup    > 0),
    CONSTRAINT ck_bexec_eficien   CHECK (eficiencia IS NULL OR eficiencia > 0)
);

COMMENT ON TABLE benchmark_execucao IS
    'Entidade associativa com atributos proprios: speedup e eficiencia so existem no contexto da comparacao (RF09, UC06).';

-- ---------------------------------------------------------------------
-- 10. LOG_EVENTO
-- ---------------------------------------------------------------------
CREATE TABLE log_evento (
    id_log        BIGSERIAL   PRIMARY KEY,
    id_usuario    INTEGER,
    id_execucao   INTEGER,
    nivel         nivel_log   NOT NULL DEFAULT 'INFO',
    origem        VARCHAR(120),
    mensagem      TEXT        NOT NULL,
    contexto      JSONB,
    registrado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT fk_log_usuario  FOREIGN KEY (id_usuario)
        REFERENCES usuario (id_usuario) ON DELETE SET NULL,
    CONSTRAINT fk_log_execucao FOREIGN KEY (id_execucao)
        REFERENCES execucao_analise (id_execucao) ON DELETE CASCADE
);

COMMENT ON TABLE log_evento IS
    'Trilha de auditoria e registro de erros capturados durante a execucao paralela (RNF de Confiabilidade).';

-- ---------------------------------------------------------------------
-- 11. INDICES
-- ---------------------------------------------------------------------
CREATE INDEX idx_dataset_usuario      ON dataset (id_usuario);
CREATE INDEX idx_transacao_dataset    ON transacao (id_dataset);
CREATE INDEX idx_transacao_atributos  ON transacao USING GIN (atributos);

CREATE INDEX idx_execucao_dataset_modo ON execucao_analise (id_dataset, modo_execucao);
CREATE INDEX idx_execucao_status       ON execucao_analise (status);
CREATE INDEX idx_execucao_criado       ON execucao_analise (criado_em DESC);

CREATE INDEX idx_resultado_execucao    ON resultado_deteccao (id_execucao);
CREATE INDEX idx_resultado_transacao   ON resultado_deteccao (id_transacao);
CREATE INDEX idx_resultado_score       ON resultado_deteccao (id_execucao, score_anomalia DESC);

-- Indice parcial: com taxa de fraude de ~0,17%, indexar apenas as linhas
-- suspeitas produz um indice centenas de vezes menor (consulta central do UC05).
CREATE INDEX idx_resultado_suspeita    ON resultado_deteccao (id_execucao, score_anomalia DESC)
    WHERE is_suspeita = TRUE;

CREATE INDEX idx_bexec_benchmark       ON benchmark_execucao (id_benchmark);
CREATE INDEX idx_log_execucao          ON log_evento (id_execucao, registrado_em DESC);

-- ---------------------------------------------------------------------
-- 12. VISOES DE APOIO
-- ---------------------------------------------------------------------

-- Alimenta as telas T07 (Resultados) e T11 (Historico)
CREATE VIEW vw_resumo_execucao AS
SELECT
    e.id_execucao,
    d.nome                AS dataset,
    d.total_registros,
    m.nome                AS modelo,
    m.algoritmo,
    u.nome                AS solicitante,
    e.modo_execucao,
    e.num_workers,
    e.tamanho_chunk,
    e.status,
    e.tempo_total_s,
    e.total_analisadas,
    e.total_suspeitas,
    CASE WHEN e.total_analisadas > 0
         THEN ROUND(100.0 * e.total_suspeitas / e.total_analisadas, 4)
         ELSE NULL END    AS taxa_suspeicao_pct,
    CASE WHEN e.tempo_total_s > 0
         THEN ROUND(e.total_analisadas / e.tempo_total_s, 2)
         ELSE NULL END    AS throughput_tps,
    mt.cpu_percent_medio,
    mt.memoria_pico_mb,
    mt.tempo_overhead_s,
    e.criado_em
FROM execucao_analise e
JOIN dataset          d  ON d.id_dataset = e.id_dataset
JOIN modelo_deteccao  m  ON m.id_modelo  = e.id_modelo
JOIN usuario          u  ON u.id_usuario = e.id_usuario
LEFT JOIN metrica_execucao mt ON mt.id_execucao = e.id_execucao;

-- Alimenta a tela T10 (Relatorio Comparativo): calcula speedup e
-- eficiencia de cada execucao em relacao ao baseline do proprio benchmark.
CREATE VIEW vw_comparativo_benchmark AS
WITH baseline AS (
    SELECT be.id_benchmark, e.tempo_total_s AS tempo_baseline
    FROM benchmark_execucao be
    JOIN execucao_analise   e ON e.id_execucao = be.id_execucao
    WHERE be.papel = 'BASELINE'
)
SELECT
    b.id_benchmark,
    b.descricao,
    d.nome              AS dataset,
    e.id_execucao,
    e.modo_execucao,
    e.num_workers,
    e.tempo_total_s,
    bl.tempo_baseline,
    ROUND(bl.tempo_baseline / NULLIF(e.tempo_total_s, 0), 4)               AS speedup,
    ROUND(bl.tempo_baseline / NULLIF(e.tempo_total_s * e.num_workers, 0), 4) AS eficiencia,
    e.total_suspeitas
FROM benchmark           b
JOIN benchmark_execucao  be ON be.id_benchmark = b.id_benchmark
JOIN execucao_analise    e  ON e.id_execucao   = be.id_execucao
JOIN dataset             d  ON d.id_dataset    = b.id_dataset
JOIN baseline            bl ON bl.id_benchmark = b.id_benchmark
ORDER BY b.id_benchmark, e.num_workers;

-- =====================================================================
-- FIM DO SCRIPT
-- =====================================================================
