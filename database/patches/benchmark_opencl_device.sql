-- Add the selected OpenCL device type to benchmark execution records.
ALTER TABLE benchmark_execucao
    ADD COLUMN IF NOT EXISTS tipo_dispositivo VARCHAR(3);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_bexec_dispositivo'
          AND conrelid = 'benchmark_execucao'::regclass
    ) THEN
        ALTER TABLE benchmark_execucao
            ADD CONSTRAINT ck_bexec_dispositivo
            CHECK (
                tipo_dispositivo IS NULL
                OR tipo_dispositivo IN ('CPU', 'GPU')
            );
    END IF;
END $$;

-- Rollback:
-- ALTER TABLE benchmark_execucao DROP CONSTRAINT IF EXISTS ck_bexec_dispositivo;
-- ALTER TABLE benchmark_execucao DROP COLUMN IF EXISTS tipo_dispositivo;
