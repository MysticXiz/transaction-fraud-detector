-- Persist the selected OpenCL device for parallel analysis executions.
ALTER TABLE execucao_analise
    ADD COLUMN IF NOT EXISTS tipo_dispositivo VARCHAR(3);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_execucao_dispositivo'
          AND conrelid = 'execucao_analise'::regclass
    ) THEN
        ALTER TABLE execucao_analise
            ADD CONSTRAINT ck_execucao_dispositivo
            CHECK (
                tipo_dispositivo IS NULL
                OR tipo_dispositivo IN ('CPU', 'GPU')
            );
    END IF;
END $$;

-- Rollback:
-- ALTER TABLE execucao_analise DROP CONSTRAINT IF EXISTS ck_execucao_dispositivo;
-- ALTER TABLE execucao_analise DROP COLUMN IF EXISTS tipo_dispositivo;
