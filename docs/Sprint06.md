# SISTEMA INTELIGENTE DE DETECÇÃO DE FRAUDES EM TRANSAÇÕES
## Documento Técnico — Sprint 06
### Terceiro módulo: análise, detecção e integração do sistema

**Grupo: 14**

**Curso:** Ciência da Computação — **Turma:** 8MB — **Instituição:** UNINASSAU  
**Disciplinas:** Fábrica de Software / Tópicos Avançados em Ciência da Computação  
**Professores:** Pryscilla de Barros Gonçalves; Antenor Jorge Parnaiba da Silva  
**Equipe:** Bruno Severino de Almeida Rocha; Rodrigo Amorim Neves; Everson Padilha Ferreira; Eduardo Barros Magalhães  
**Repositório:** https://github.com/MysticXiz/transaction-fraud-detector

---

## 1. Continuidade e objetivo da Sprint

As Sprints 01 a 05 definiram o problema e a arquitetura, estruturaram a aplicação, implementaram autenticação e gestão de usuários e entregaram o segundo módulo funcional: gestão e ingestão de datasets. A avaliação da Sprint 05 destacou que o sistema precisava avançar para o núcleo analítico, apresentar resultados reais dos testes, documentar problemas corrigidos, identificar claramente o Grupo 14 e registrar os commits.

Esta Sprint implementa o **terceiro módulo**, responsável pelo processamento analítico dos datasets e pela detecção de transações suspeitas. O módulo utiliza os dados importados, executa análises e benchmarks, persiste o estado e os resultados e disponibiliza os fluxos pela interface. Também foram reforçados o controle de acesso, o isolamento entre usuários, a navegação e o acompanhamento de tarefas demoradas.

## 2. Ações realizadas e terceiro módulo implementado

### 2.1 Análise e detecção

- Integração do pré-processamento e do executor Isolation Forest ao fluxo de análise.
- Consulta das capacidades de dispositivos OpenCL e seleção do tipo de dispositivo disponível na análise e no benchmark.
- Configuração de modo de execução, quantidade de workers, tamanho de chunk e limiar de decisão.
- Persistência das execuções, resultados e métricas para consulta posterior.
- Exportação de resultados e consulta dos detalhes das transações classificadas.

Endpoints principais: `GET /analises/capacidades`, `POST /analises`, `GET /analises`, `GET /analises/{execution_id}` e rotas de resultados/exportação em [`analyses.py`](../backend/src/fraud_detector/api/routes/analyses.py).

### 2.2 Benchmark e processamento demorado

- Integração do benchmark com datasets, modelos e opções de execução do módulo analítico.
- Acompanhamento de progresso e consulta de relatórios persistidos.
- Registro persistido de importações e solicitações de cancelamento para tarefas longas, com atualização de estado pelo backend.
- Gerenciador no frontend para acompanhar importações, análises e benchmarks sem bloquear a navegação; as tarefas são consultadas pelo estado registrado no servidor.

Endpoints principais: `GET /benchmarks/capacidades`, `POST /benchmarks`, `GET /benchmarks/{benchmark_id}` e exportação do relatório em [`benchmarks.py`](../backend/src/fraud_detector/api/routes/benchmarks.py). Os fluxos de importação em segundo plano estão em [`datasets.py`](../backend/src/fraud_detector/api/routes/datasets.py).

### 2.3 Acesso e isolamento de dados

- ADMIN e ANALISTA podem executar operações de escrita; VISUALIZADOR fica limitado a consultas.
- Consultas e alterações de transações são limitadas aos datasets pertencentes ao usuário autenticado.
- Dados de datasets e jobs são filtrados por proprietário; a mesma impressão digital de arquivo pode ser usada por contas diferentes, sem permitir acesso cruzado.
- Ao trocar de usuário, o frontend limpa tarefas e inscrições de acompanhamento mantidas em memória.

As regras de autorização ficam em [`roles.py`](../backend/src/fraud_detector/api/dependencies/roles.py), e a filtragem de transações por proprietário em [`transaction_repository.py`](../backend/src/fraud_detector/infrastructure/repositories/transaction_repository.py).

## 3. Integração entre os módulos

O fluxo integrado para demonstração é:

1. Autenticar-se e acessar o painel com uma conta ANALISTA ou ADMIN.
2. Importar um CSV pelo módulo de datasets e acompanhar o processamento até a confirmação de persistência.
3. Selecionar o dataset importado, consultar as capacidades do dispositivo e configurar uma análise.
4. Acompanhar a execução pelo gerenciador de processos e abrir seus resultados, métricas e detalhes de transações.
5. Executar um benchmark com o mesmo dataset/modelo e consultar ou exportar o relatório.
6. Entrar com uma conta VISUALIZADOR e confirmar que os dados próprios podem ser consultados, mas ações de escrita e execução não ficam disponíveis.
7. Alternar entre contas e confirmar que tarefas da sessão anterior não permanecem no gerenciador.

Essa integração conecta autenticação e permissões, ingestão de datasets, processamento analítico, resultados e benchmarking. As rotas de leitura e exportação permanecem disponíveis conforme a propriedade e o papel do usuário.

## 4. Evidências verificáveis

### 4.1 Execução local registrada

Validações executadas após as correções de formatação:

| Verificação | Resultado observado |
|---|---|
| `python -m black --check backend/ tests/` | Sucesso — 57 arquivos sem necessidade de reformatação |
| `python -m ruff check backend/ tests/` | Sucesso — todos os checks passaram |
| `python -m pytest tests/ -q` | **53 passaram, 1 ignorado** |
| `npm run build` em `frontend/` | Sucesso — bundle Angular gerado |
| `python -m compileall -q backend/src/fraud_detector` | Sucesso |

O arquivo [`test_results_metrics_contract.py`](../tests/unit/test_results_metrics_contract.py) verifica contratos de análise/benchmark, autorização das rotas mutáveis e o formato esperado pelas telas. Os testes de ingestão e processamento estão em [`test_dataset_ingestion.py`](../tests/unit/test_dataset_ingestion.py) e [`test_opencl_isolation_forest.py`](../tests/unit/test_opencl_isolation_forest.py).

### 4.2 Pipeline do GitHub Actions

A primeira execução após a integração, [pipeline #15](https://github.com/MysticXiz/transaction-fraud-detector/actions/runs/39057030440), falhou na verificação do Black: seis arquivos Python precisavam de formatação. O Ruff e o Pytest foram ignorados nessa execução. A correção foi aplicada no commit `700d52b`, e a execução seguinte, [pipeline #16](https://github.com/MysticXiz/transaction-fraud-detector/actions/runs/39057206664), foi concluída com sucesso: instalação, Black, Ruff e Pytest passaram no GitHub Actions.

Os resultados locais da tabela e o resultado remoto bem-sucedido da pipeline foram verificados antes de fechar este documento.

### 4.3 Roteiro de demonstração e captura de evidências

Use a aplicação com o PostgreSQL configurado e registre capturas reais das seguintes telas/respostas:

1. Importação de um dataset concluída e dataset visível na lista.
2. Configuração de análise com dispositivo/workers selecionados.
3. Processo em andamento e resultado concluído, incluindo métricas e transações.
4. Benchmark concluído e relatório consultável/exportável.
5. Acesso VISUALIZADOR: consulta disponível e ações de escrita ausentes; alternância de conta sem processos da conta anterior.

Não foram anexadas capturas de tela nesta execução; não foram substituídas por imagens ou resultados simulados. Os resultados da tabela acima e os logs da pipeline são evidências automatizadas reproduzíveis.

## 5. Melhorias de interface e navegação

- Páginas de análise e benchmark expõem seleção de dispositivo e configuração coerente com as capacidades detectadas.
- Importações, análises e benchmarks longos são acompanhados no gerenciador de processos, que apresenta progresso, estado, erro e opção de cancelamento quando aplicável.
- A lista de datasets, o painel, o histórico e o shell exibem ações compatíveis com o papel do usuário.
- Rotas de criação/importação/análise/benchmark são protegidas também por guardas de navegação; a autorização definitiva continua no backend.
- A conta VISUALIZADOR vê os dados do perfil, mas não recebe controles de edição.

## 6. Bugs e problemas principais tratados

| Problema observado | Correção implementada | Evidência |
|---|---|---|
| O papel VISUALIZADOR conseguia chamar operações de escrita diretamente pela API, mesmo que a interface escondesse alguns controles. | Dependência central de escrita aplicada às rotas mutáveis; autorização testada para ADMIN, ANALISTA e bloqueio do VISUALIZADOR. | Testes em `test_results_metrics_contract.py`; pipeline e suite de Pytest. |
| Consultas CRUD de transações não eram limitadas ao dono do dataset. | Repositório agora filtra por `DatasetModel.id_usuario`; transações de datasets de outra conta não são retornadas, alteradas ou excluídas. | Testes de autorização/contrato e integração do repositório. |
| O estado em memória do gerenciador podia exibir processos da sessão anterior depois de trocar de usuário. | Limpeza de tarefas e subscriptions quando a identidade autenticada muda; acompanhamento não cancela jobs da conta anterior. | Fluxo reproduzível de alternância de contas descrito na seção 3. |
| A unicidade global do hash de arquivo impedia contas distintas de importar o mesmo conteúdo. | Unicidade ajustada para ser por usuário, preservando a prevenção de duplicidade dentro da mesma conta. | Patch `database/patches/dataset_hash_per_user.sql` e testes de ingestão. |
| A primeira CI da entrega parou antes de executar lint e testes por divergências do Black. | Seis arquivos formatados; Black e Ruff executados localmente, seguidos pela suite Pytest. | Resultados locais e pipeline #15/#16. |

## 7. Mudanças separadas por branch

| Branch | Mudanças desta Sprint |
|---|---|
| `feature/frontend-integracao` | Implementação integrada do módulo analítico, seleção OpenCL, benchmarks e acompanhamento/cancelamento de processos; reforço de permissões e isolamento por usuário; ajustes de interface, navegação e testes. Também recebeu a correção de formatação exigida pela CI. |
| `develop` | Recebeu a integração da branch de implementação e, depois, a integração da correção de formatação. Não foram feitas alterações funcionais distintas diretamente em `develop` nesta entrega. |

As branches `feature/resultados-metricas` e `feature/testes-documentacao` já continham trabalho anterior integrado à base de `develop`; não receberam alterações específicas nesta Sprint.

## 8. Histórico dos commits de implementação e integração desta Sprint

| Commit | Branch | Descrição |
|---|---|---|
| `d7130e1` | `feature/frontend-integracao` | Implementa processamento e isolamento por usuário |
| `700d52b` | `feature/frontend-integracao` | Aplica formatação Black exigida pela CI |
| `c311cf6` | `develop` | Merge feature/frontend-integracao into develop |
| `bce4f3f` | `develop` | Merge correção de formatação CI em develop |

O repositório completo, com os commits e branches publicados, está em https://github.com/MysticXiz/transaction-fraud-detector.
O commit que versiona este documento também está registrado no histórico da branch `develop`.

## 9. Dificuldades encontradas e próximos passos

### Dificuldades

- A disponibilidade de CPU/GPU OpenCL depende dos dispositivos e runtimes instalados em cada máquina; por isso, a interface consulta as capacidades em vez de presumir que todo tipo de dispositivo está disponível.
- Importações, análises e benchmarks podem durar mais que uma requisição HTTP; foi necessário persistir estados e separar o acompanhamento/cancelamento do ciclo de vida da tela.
- O isolamento exigiu propagar a identidade do usuário até o repositório de transações e rever a regra de duplicidade de datasets.
- A CI da primeira integração revelou formatação fora do padrão antes de executar Ruff e Pytest; o problema foi corrigido e a pipeline foi reenviada.

### Próximos passos

1. Aplicar os patches SQL pendentes nos bancos já existentes: `database/patches/analysis_opencl_device.sql`, `benchmark_opencl_device.sql`, `cancellable_jobs.sql` e `dataset_hash_per_user.sql`.
2. Executar o roteiro integrado com PostgreSQL e capturar as evidências de tela indicadas na seção 4.3.
3. Demonstrar o acesso com os três papéis e a alternância entre contas usando dados separados.
4. Repetir a validação em ambiente com dispositivos OpenCL disponíveis e documentar quais dispositivos foram detectados.
5. Manter as verificações automatizadas da CI em novas alterações; a pipeline #16 validou com sucesso a implementação integrada.

---

**Conclusão:** a Sprint 06 transforma o núcleo analítico previsto nas Sprints anteriores em um fluxo integrado de ingestão, análise, detecção e benchmark. Além da entrega funcional, foram registrados resultados reais dos testes, os problemas principais e suas correções, o histórico completo de commits desta Sprint e as mudanças por branch, conforme os pontos de atenção da avaliação anterior.
