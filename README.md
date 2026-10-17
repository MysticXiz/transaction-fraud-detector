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