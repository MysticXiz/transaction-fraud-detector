# Detector de Fraudes em Transações

## Pré-processamento

O pré-processador está disponível em
`src.fraud_detector.computational.preprocessing.preprocessor`. Ele recebe um
`pandas.DataFrame` com atributos das transações, exclui rótulos e
identificadores, converte valores inválidos em ausentes, imputa a mediana,
padroniza `Time` e `Amount` (ou `tempo_relativo` e `valor`) e retorna uma
matriz NumPy contígua.

```python
import pandas as pd

from src.fraud_detector.computational.preprocessing.preprocessor import Preprocessor

transacoes = pd.DataFrame([
    {"Time": 1.0, "Amount": 10.0, "V1": 0.12, "Class": 0},
    {"Time": 2.0, "Amount": 25.0, "V1": -0.08, "Class": 0},
])
preprocessor = Preprocessor()
features = preprocessor.fit_transform(transacoes)

print(preprocessor.feature_names)
print(features)
```

O rótulo real (`Class`, `label`, `rotulo` ou equivalente) não é usado como
feature. Para preparar novos dados com as mesmas colunas, use
`preprocessor.transform(novas_transacoes)` após ajustar o pré-processador.

## Execução paralela com OpenCL

`OpenCLIsolationForestExecutor`, em
`src.fraud_detector.computational.execution.opencl_isolation_forest`, ajusta o
Isolation Forest de referência e calcula os escores de anomalia em um kernel
OpenCL. Cada work-item percorre as árvores para uma transação, e os resultados
mantêm a ordem de entrada mesmo quando processados em chunks.

O executor precisa do pacote PyOpenCL e de um runtime/driver OpenCL compatível
com o dispositivo. Ele prefere um dispositivo GPU quando disponível e também
aceita um dispositivo CPU OpenCL. Não há fallback silencioso para a pontuação
paralela em CPU.

No benchmark, a configuração paralela permite escolher entre dispositivos CPU
e GPU OpenCL detectados pelo backend. A opção de CPU também exige que o runtime
OpenCL instalado exponha um dispositivo CPU; ela não representa apenas a
execução sequencial de referência.

```python
import pandas as pd

from src.fraud_detector.computational.preprocessing.preprocessor import Preprocessor
from src.fraud_detector.computational.execution.opencl_isolation_forest import (
    OpenCLIsolationForestExecutor,
)

transactions = pd.DataFrame([
    {"Time": 1.0, "Amount": 10.0, "V1": 0.12, "Class": 0},
    {"Time": 2.0, "Amount": 25.0, "V1": -0.08, "Class": 0},
    {"Time": 3.0, "Amount": 800.0, "V1": 9.5, "Class": 1},
])
features = Preprocessor().fit_transform(transactions)
result = OpenCLIsolationForestExecutor(
    n_estimators=50, contamination=0.05
).execute(features, threshold=0.5, chunk_size=2)
```

O treinamento do Isolation Forest continua no scikit-learn, em CPU. A etapa
paralela que percorre as árvores e calcula os escores roda em OpenCL. As rotas
de análise do frontend não são implementadas por este executor; sua integração
com `/analises` permanece na camada da API.

## Cancelamento de importações e benchmarks

Importações de datasets e benchmarks são registrados no banco para que o
cancelamento solicitado pelo frontend também seja observado pelo backend. A
importação verifica o pedido durante a leitura e a gravação em lote; ao cancelar,
a transação do dataset é revertida e o arquivo temporário é removido. Benchmark e
análise param cooperativamente entre etapas/chunks, então uma etapa indivisível
que já esteja executando pode terminar antes do cancelamento.

Em bancos existentes, aplique `database/patches/cancellable_jobs.sql` antes de
usar esses fluxos. Para reverter a alteração, execute em ordem os comandos no
bloco `Rollback` ao final desse patch. A criação de novas bases já inclui a tabela
e os campos necessários em `database/schema.sql`.

Os endpoints de importação de job são `POST /datasets/importacoes`,
`POST /datasets/importacoes/{id}/arquivo`, `GET /datasets/importacoes/{id}` e
`POST /datasets/importacoes/{id}/cancelar`. Benchmarks são cancelados em
`POST /benchmarks/{id}/cancelar`. Os estados ficam persistidos, mas a execução
usa `BackgroundTasks` do FastAPI: um reinício do servidor durante um job pode
deixar seu estado não terminal no banco, pois ainda não há uma fila de tarefas
durável.

Para escolher CPU ou GPU OpenCL no benchmark, aplique também
`database/patches/benchmark_opencl_device.sql` a bancos existentes. O endpoint
`GET /benchmarks/capacidades` retorna os dispositivos OpenCL disponíveis; a
seleção fica registrada em cada execução do benchmark. O bloco `Rollback` do
patch reverte essa alteração.

A tela de análise paralela usa os mesmos dispositivos e limites. Em bancos
existentes, aplique `database/patches/analysis_opencl_device.sql` para persistir
a seleção por execução; o endpoint `GET /analises/capacidades` fornece os
dispositivos detectados e o patch contém instruções de rollback.

Para permitir que usuários diferentes importem o mesmo arquivo sem permitir
duplicatas para o mesmo usuário, aplique
`database/patches/dataset_hash_per_user.sql` em bancos existentes. O patch
inclui rollback; o schema de novas instalações já usa unicidade por usuário.