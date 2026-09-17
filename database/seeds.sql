-- =====================================================================
-- Carga inicial - Sprint 02
-- Executar apos schema.sql
-- Senhas sao hashes bcrypt de exemplo (ambiente de desenvolvimento).
-- =====================================================================

INSERT INTO usuario (nome, email, senha_hash, papel) VALUES
 ('Bruno Severino de Almeida Rocha', 'bruno@uninassau.local',
  '$2b$12$devPlaceholderHashBrunoXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX', 'ADMIN'),
 ('Rodrigo Amorim Neves',            'rodrigo@uninassau.local',
  '$2b$12$devPlaceholderHashRodrigoXXXXXXXXXXXXXXXXXXXXXXXXXXXX', 'ANALISTA'),
 ('Everson Padilha Ferreira',        'everson@uninassau.local',
  '$2b$12$devPlaceholderHashEversonXXXXXXXXXXXXXXXXXXXXXXXXXXXX', 'ANALISTA');

INSERT INTO modelo_deteccao
 (nome, algoritmo, versao, hiperparametros, limiar_padrao, caminho_artefato)
VALUES
 ('Isolation Forest - Baseline', 'ISOLATION_FOREST', '1.0.0',
  '{"n_estimators": 200, "max_samples": "auto", "contamination": 0.0017, "random_state": 42, "n_jobs": 1}'::jsonb,
  0.5000, 'artifacts/iforest_v1.joblib'),

 ('Regressao Logistica - Referencia', 'LOGISTIC_REGRESSION', '1.0.0',
  '{"class_weight": "balanced", "max_iter": 1000, "solver": "liblinear", "random_state": 42}'::jsonb,
  0.5000, 'artifacts/logreg_v1.joblib');

-- Observacao: "n_jobs": 1 no Isolation Forest e deliberado.
-- O scikit-learn paralelizaria internamente com n_jobs=-1, o que invalidaria
-- a comparacao entre execucao sequencial e paralela (RF09). O paralelismo
-- deve ser controlado exclusivamente pelo ParallelExecutor do projeto.
