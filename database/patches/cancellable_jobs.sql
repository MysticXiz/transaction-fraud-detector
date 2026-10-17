-- Apply to databases created before persisted benchmark/import cancellation.
ALTER TABLE benchmark
    ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'PENDENTE';
ALTER TABLE benchmark
    ADD COLUMN IF NOT EXISTS mensagem_erro TEXT;

UPDATE benchmark AS b
SET status = CASE
    WHEN EXISTS (
        SELECT 1
        FROM benchmark_execucao AS be
        JOIN execucao_analise AS e ON e.id_execucao = be.id_execucao
        WHERE be.id_benchmark = b.id_benchmark
          AND e.status = 'CANCELADA'
    ) THEN 'CANCELADO'
    WHEN EXISTS (
        SELECT 1
        FROM benchmark_execucao AS be
        JOIN execucao_analise AS e ON e.id_execucao = be.id_execucao
        WHERE be.id_benchmark = b.id_benchmark
          AND e.status = 'FALHA'
    ) THEN 'FALHA'
    WHEN EXISTS (
        SELECT 1
        FROM benchmark_execucao AS be
        JOIN execucao_analise AS e ON e.id_execucao = be.id_execucao
        WHERE be.id_benchmark = b.id_benchmark
          AND e.status <> 'CONCLUIDA'
    ) THEN 'EM_ANDAMENTO'
    ELSE 'CONCLUIDO'
END;

CREATE TABLE IF NOT EXISTS dataset_import_job (
    id_importacao SERIAL PRIMARY KEY,
    id_usuario INTEGER NOT NULL REFERENCES usuario (id_usuario) ON DELETE CASCADE,
    nome VARCHAR(160) NOT NULL,
    origem VARCHAR(80) NOT NULL,
    descricao TEXT,
    nome_arquivo VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDENTE',
    cancelamento_solicitado BOOLEAN NOT NULL DEFAULT FALSE,
    mensagem_erro TEXT,
    id_dataset INTEGER REFERENCES dataset (id_dataset) ON DELETE SET NULL,
    criado_em TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Rollback:
-- DROP TABLE dataset_import_job;
-- ALTER TABLE benchmark DROP COLUMN mensagem_erro;
-- ALTER TABLE benchmark DROP COLUMN status;
