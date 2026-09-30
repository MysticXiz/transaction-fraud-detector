-- Remove índices de transacao que encarecem ingestão/exclusão em massa
-- e não atendem consultas do sistema.
-- Seguro em banco já criado a partir do schema anterior.

DROP INDEX IF EXISTS idx_transacao_atributos;
DROP INDEX IF EXISTS idx_transacao_dataset;
