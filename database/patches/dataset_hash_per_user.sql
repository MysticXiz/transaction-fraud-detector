-- Allow different users to import the same file while preventing duplicates
-- for the same user.
ALTER TABLE dataset DROP CONSTRAINT IF EXISTS uk_dataset_hash;
ALTER TABLE dataset DROP CONSTRAINT IF EXISTS dataset_hash_arquivo_key;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'uk_dataset_usuario_hash'
          AND conrelid = 'dataset'::regclass
    ) THEN
        ALTER TABLE dataset
            ADD CONSTRAINT uk_dataset_usuario_hash
            UNIQUE (id_usuario, hash_arquivo);
    END IF;
END $$;

-- Rollback (only after ensuring no duplicate hashes exist across users):
-- ALTER TABLE dataset DROP CONSTRAINT IF EXISTS uk_dataset_usuario_hash;
-- ALTER TABLE dataset ADD CONSTRAINT uk_dataset_hash UNIQUE (hash_arquivo);
