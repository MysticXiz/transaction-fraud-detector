-- =====================================================================
-- Carga inicial - Sprint 02
-- O usuario administrador inicial e criado pela aplicacao na inicializacao.
-- =====================================================================

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
