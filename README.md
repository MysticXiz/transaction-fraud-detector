# Detector de Fraudes em Transações

## Pré-processamento

O pré-processador está disponível em
`src.fraud_detector.computational.preprocessing.preprocessor`. Ele recebe um
`pandas.DataFrame` com atributos das transações, exclui rótulos e
identificadores, converte valores inválidos em ausentes, imputa a mediana,
padroniza `Time` e `Amount` (ou `tempo_relativo` e `valor`) e retorna uma
matriz NumPy contígua. A implementação cobre apenas a preparação dos dados;
detecção de fraude e execução analítica serão especificadas separadamente.

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