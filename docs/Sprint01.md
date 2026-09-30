# Sistema Inteligente de Detecção de Fraudes em Transações
## Documento Técnico — Sprint 01
> **Proposta Inicial de Projeto**  
> Fábrica de Software e Tópicos Avançados em Ciência da Computação

---

## Sumário

1. [Identificação da Equipe](#1-identificação-da-equipe)
2. [Escolha do Tema](#2-escolha-do-tema)
3. [Definição do Problema](#3-definição-do-problema)
4. [Objetivos do Sistema](#4-objetivos-do-sistema)
5. [Público-Alvo](#5-público-alvo)
6. [Requisitos Funcionais](#6-requisitos-funcionais)
7. [Requisitos Não Funcionais](#7-requisitos-não-funcionais)
8. [Casos de Uso](#8-casos-de-uso)
9. [Product Backlog](#9-product-backlog)
10. [Cronograma Inicial](#10-cronograma-inicial)
11. [Repositório GitHub](#11-repositório-github)

---

## 1. Identificação da Equipe

- **Nome do projeto:** Sistema Inteligente de Detecção de Fraudes em Transações
- **Subtítulo provisório:** Plataforma Escalável de Análise de Anomalias Financeiras por meio de Processamento Paralelo
  - *Provisório – Sujeito a alterações*
- **Integrantes:**
  - Integrante 1: Bruno Severino de Almeida Rocha
  - Integrante 2: Rodrigo Amorim Neves
  - Integrante 3: Everson Padilha Ferreira
- **Turma:** 8MB
- **Curso:** Ciência da Computação
- **Instituição:** UNINASSAU
- **Disciplinas envolvidas:**
  - Fábrica de Software
  - Tópicos Avançados em Ciência da Computação
- **Professor(es):**
  - Fábrica de Software: Pryscilla de Barros Gonçalves
  - Tópicos Avançados em Ciência da Computação: Antenor Jorge Parnaiba da Silva

---

## 2. Escolha do Tema

O presente projeto insere-se no contexto do desenvolvimento de sistemas inteligentes e de alto desempenho aplicados ao setor financeiro.

### Principais áreas de conhecimento

- Inteligência Artificial
- Aprendizado de Máquina
- Ciência de Dados
- Processamento de Grandes Volumes de Dados
- Detecção de Anomalias
- Segurança de Sistemas Financeiros
- Computação Paralela

No cenário financeiro moderno, a transição contínua para meios de pagamento digitais gera um fluxo ininterrupto e massivo de transações. A identificação tempestiva de comportamentos potencialmente fraudulentos torna-se um desafio crítico, exigindo abordagens automatizadas capazes de examinar padrões complexos de dados sem comprometer o tempo de resposta do sistema.

Por tratar-se de uma iniciativa acadêmica integrada às disciplinas de Fábrica de Software e Tópicos Avançados em Ciência da Computação, o projeto utilizará conjuntos de dados apropriados para fins de testes e desenvolvimento, priorizando a utilização de dados públicos anonimizados ou bases sintéticas que simulem cenários reais de transações financeiras.

---

## 3. Definição do Problema

### Questão central

> **Como identificar automaticamente transações potencialmente fraudulentas em grandes volumes de dados, utilizando técnicas de inteligência artificial e processamento paralelo em CPU, de maneira eficiente e escalável?**

### Observações do domínio

- **Volume de dados:** Sistemas financeiros processam milhares a milhões de registros diariamente, gerando uma massa de dados cuja análise manual é inviável.
- **Complexidade de padrões:** Fraudes financeiras raramente seguem regras estáticas simples, manifestando-se frequentemente por meio de correlações sutis e anomalias multidimensionais.
- **Agilidade na detecção:** A retenção de perdas financeiras depende diretamente da capacidade de identificar transações suspeitas o mais rápido possível.
- **Custo computacional:** A aplicação de modelos preditivos ou de detecção de anomalias sobre grandes volumes de registros exige capacidade considerável de processamento.
- **Paralelização de tarefas:** A distribuição da carga de trabalho entre múltiplos núcleos de CPU permite que diferentes subconjuntos de transações sejam analisados simultaneamente, mitigando gargalos de desempenho.

A resolução desse problema apresenta grande relevância para instituições financeiras, operadoras de cartão de crédito e plataformas de e-commerce, permitindo mitigar prejuízos operacionais e proteger os usuários finais contra movimentações não autorizadas.

---

## 4. Objetivos do Sistema

### 4.1 Objetivo geral

Desenvolver um sistema computacional capaz de analisar conjuntos de dados contendo transações financeiras e identificar aquelas que apresentam características potencialmente fraudulentas, utilizando técnicas de inteligência artificial / aprendizado de máquina e arquiteturas de processamento paralelo em CPU para otimização do desempenho.

### 4.2 Objetivos específicos

- Processar conjuntos de dados contendo histórico e registros de transações financeiras;
- Realizar o tratamento, higienização e pré-processamento dos dados para entrada nos modelos analíticos;
- Mapear e extrair características (*features*) relevantes para a identificação de fraudes;
- Desenvolver e integrar um mecanismo de classificação ou detecção de anomalias;
- Estruturar um *pipeline* de processamento paralelo para distribuir a análise entre múltiplos processos de CPU;
- Comparar empiricamente o desempenho entre a execução sequencial e a execução paralela;
- Avaliar métricas computacionais do sistema sob diferentes volumes de dados;
- Sinalizar e isolar transações classificadas como potencialmente fraudulentas;
- Apresentar relatórios e resultados da análise de forma compreensível ao usuário;
- Construir uma arquitetura de software organizada, modular e sustentável.

---

## 5. Público-Alvo

Os potenciais usuários e beneficiários do sistema englobam:

- Instituições financeiras e fintechs;
- Empresas processadoras de meios de pagamento;
- Plataformas de comércio eletrônico (*e-commerce*);
- Organizações que movimentam grandes volumes diários de transações digitais;
- Analistas de risco, fraude e conformidade;
- Profissionais e pesquisadores das áreas de segurança e análise de dados;
- Estudantes e acadêmicos interessados nas aplicações práticas de Inteligência Artificial e Computação Paralela.

No âmbito deste projeto acadêmico, a solução será estruturada como um protótipo funcional voltado para demonstração prática, testes de desempenho e validação conceitual das técnicas empregadas.

---

## 6. Requisitos Funcionais

| Código | Requisito | Descrição |
|---|---|---|
| **RF01** | Importar dados de transações | O sistema deverá permitir a importação de conjuntos de dados contendo transações para análise. |
| **RF02** | Validar os dados | O sistema deverá verificar se os dados importados possuem a estrutura e os campos mínimos necessários para o processamento. |
| **RF03** | Pré-processar os dados | O sistema deverá realizar etapas de limpeza, padronização e transformação dos dados brutos. |
| **RF04** | Executar análise de transações | O sistema deverá analisar as transações utilizando um mecanismo de inteligência artificial, aprendizado de máquina ou detecção de anomalias. |
| **RF05** | Processar transações em paralelo | O sistema deverá permitir a divisão do conjunto de dados em partes para processamento simultâneo via múltiplos processos da CPU. |
| **RF06** | Identificar transações suspeitas | O sistema deverá sinalizar e rotular transações identificadas como potencialmente fraudulentas. |
| **RF07** | Apresentar resultados | O sistema deverá exibir os resultados da análise ao usuário em formato estruturado. |
| **RF08** | Exibir informações da análise | O sistema deverá fornecer métricas sobre a execução, tais como total de transações analisadas, quantidade de suspeitas e tempo de processamento. |
| **RF09** | Comparar processamento sequencial e paralelo | O sistema deverá permitir a execução comparativa entre os modos sequencial e paralelo para avaliação de ganho de desempenho. |
| **RF10** | Registrar resultados *(Proposto)* | O sistema poderá oferecer a opção de exportar ou salvar o histórico das análises realizadas em arquivo ou banco de dados. *Funcionalidade proposta, sujeita à validação da equipe.* |
| **RF11** | Configuração do número de processos *(Proposto)* | O sistema poderá permitir que o usuário defina explicitamente a quantidade de processos de CPU a serem alocados. *Funcionalidade proposta, sujeita à validação da equipe.* |

---

## 7. Requisitos Não Funcionais

### 7.1 Desempenho

- O sistema deverá processar grandes volumes de transações de forma eficiente;
- O sistema deverá empregar paralelização em CPU para reduzir o tempo total de execução em cenários com grande volume de dados;
- O sistema deverá fornecer mecanismos internos para medição precisa do tempo de execução das rotinas de análise.

### 7.2 Paralelização

- A arquitetura do sistema deverá utilizar múltiplos processos de CPU para evitar gargalos causados pelo Global Interpreter Lock (GIL) da linguagem;
- A quantidade de processos alocados deverá ser parametrizável;
- O sistema deverá possibilitar a avaliação empírica de escala com diferentes quantidades de núcleos de CPU;
- A estratégia de divisão de tarefas deverá garantir que a paralelização não altere o resultado final da classificação em comparação à execução sequencial.

### 7.3 Segurança

- O projeto utilizará estritamente dados públicos, anonimizados ou sintéticos;
- Nenhuma informação pessoal identificável real ou credencial financeira autêntica será armazenada ou processada sem o devido consentimento e conformidade legal.

### 7.4 Usabilidade

- As saídas e relatórios do sistema deverão ser claros e intuitivos;
- As interfaces (via linha de comando, API ou interface gráfica) deverão possuir comandos ou fluxos objetivos;
- O usuário deverá conseguir disparar análises operacionais sem a necessidade de alterar configurações internas do código.

### 7.5 Manutenibilidade

- O código fonte deverá ser estruturado de forma modular e separado por responsabilidades;
- A lógica do motor analítico deverá permanecer independente da camada de apresentação ou de interfaces de usuário;
- O projeto adotará controle de versão padronizado ao longo de todo o desenvolvimento.

### 7.6 Portabilidade

- O backend e o processamento principal do sistema deverão ser desenvolvidos integralmente em Python;
- O sistema deverá ser executável em ambientes operacionais padrão que suportem o ecossistema Python 3.x.

### 7.7 Confiabilidade

- O sistema deverá tratar exceções e inconsistências no formato dos arquivos de entrada sem interromper abruptamente a aplicação;
- Erros durante a execução paralela deverão ser capturados e reportados ao usuário.

---

## 8. Casos de Uso

| Código | Nome | Ator | Descrição |
|---|---|---|---|
| **UC01** | Importar conjunto de transações | Usuário / Analista | O usuário seleciona e fornece o arquivo ou conjunto de dados de entrada para o sistema. |
| **UC02** | Executar análise de fraude | Usuário / Analista | O usuário solicita o início do processamento de detecção de fraudes sobre os dados carregados. |
| **UC03** | Executar processamento paralelo | Sistema | O sistema particiona os dados e distribui os blocos de transações entre os processos da CPU. |
| **UC04** | Identificar transações suspeitas | Sistema | O mecanismo de IA/anomalias analisa os registros e classifica os eventos potencialmente fraudulentos. |
| **UC05** | Consultar resultados | Usuário / Analista | O usuário visualiza a lista de transações marcadas como suspeitas e os sumários gerados. |
| **UC06** | Comparar processamento | Usuário / Analista | O usuário executa o benchmark comparativo entre os modos sequencial e paralelo. |
| **UC07** | Consultar métricas de processamento | Usuário / Analista | O usuário analisa o tempo de execução, número de núcleos utilizados e taxas de throughput. |

---

## 9. Product Backlog

| ID | História / Funcionalidade | Descrição | Prioridade | Status | Critério de Aceite |
|---|---|---|---|---|---|
| **PB01** | Configuração inicial do projeto | Estruturação do ambiente de desenvolvimento e padrões de código. | Alta | Não iniciado | Ambiente Python configurado e padronizado para a equipe. |
| **PB02** | Criação do repositório | Criação do repositório remoto no GitHub com controle de versão. | Alta | Não iniciado | Repositório acessível com estrutura base de pastas e README. |
| **PB03** | Definição da arquitetura | Mapeamento dos módulos de dados, IA, paralelização e API. | Alta | Não iniciado | Documento técnico arquitetural preliminar aprovado. |
| **PB04** | Obtenção dos dados | Identificação e seleção do conjunto de dados sintético ou público. | Alta | Não iniciado | Base de dados baixada e armazenada no ambiente do projeto. |
| **PB05** | Módulo de importação | Como usuário, quero importar arquivos de transações para análise. | Alta | Não iniciado | Módulo lê arquivos de dados e valida formatos suportados. |
| **PB06** | Pré-processamento | Como sistema, quero limpar e normalizar os dados de entrada. | Alta | Não iniciado | Pipeline converte dados brutos em vetores prontos para o modelo. |
| **PB07** | Análise exploratória | Exploração dos dados para identificar correlações e atributos relevantes. | Média | Não iniciado | Relatório interno ou notebook com a caracterização dos dados. |
| **PB08** | Mecanismo de detecção | Como sistema, quero aplicar um modelo de IA para identificar fraudes. | Alta | Não iniciado | Modelo/algoritmo funcional classificando transações de teste. |
| **PB09** | Processamento sequencial | Implementação da rotina de execução sequencial (baseline). | Alta | Não iniciado | Execução sequencial completa com medição de tempo funcional. |
| **PB10** | Implementação de paralelização | Como sistema, quero distribuir o processamento em múltiplos núcleos de CPU. | Alta | Não iniciado | Carga dividida entre múltiplos processos de CPU com sucesso. |
| **PB11** | Parametrização de processos | Como usuário, quero definir o número de workers da CPU. | Média | Não iniciado | Parâmetro aceita alteração de quantidade de processos ativos. |
| **PB12** | Módulo de benchmarking | Como usuário, quero comparar o tempo de execução sequencial vs paralelo. | Média | Não iniciado | Relatório comparativo gerado contendo tempos de resposta. |
| **PB13** | Medição de recursos | Coleta de métricas de uso de CPU e memória durante a execução. | Baixa | Não iniciado | Métricas de uso do sistema exibidas ao final do processo. |
| **PB14** | API / Backend Python | Como sistema, quero expor endpoints para integração com serviços. | Média | Não iniciado | API REST básica rodando e respondendo a requisições HTTP. |
| **PB15** | Interface do usuário *(Opcional)* | Como usuário, quero uma interface para carregar dados e ver relatórios. | Baixa | Não iniciado | Frontend web básico consumindo a API do backend. |
| **PB16** | Persistência dos resultados | Armazenamento do histórico das classificações executadas. | Baixa | Não iniciado | Resultados salvos em banco de dados ou arquivo local. |
| **PB17** | Testes unitários e integração | Construção de suítes de testes para garantia da qualidade do código. | Média | Não iniciado | Módulos principais cobertos por testes automatizados. |
| **PB18** | Validação experimental | Validação da acurácia e eficiência do sistema sob carga. | Média | Não iniciado | Experimentos concluídos e documentados em relatórios. |
| **PB19** | Documentação do projeto | Elaboração do documento técnico final e guia do usuário. | Alta | Não iniciado | Documentação completa e alinhada ao repositório. |
| **PB20** | Preparação da apresentação | Elaboração do material para demonstração e defesa do projeto. | Alta | Não iniciado | Apresentação e ambiente de demonstração preparados. |

---

## 10. Cronograma Inicial

> As datas e prazos específicos serão atualizados conforme a disponibilização do calendário acadêmico oficial.

| Etapa | Período | Atividades | Status |
|---|---|---|---|
| **Levantamento** | Setembro | Definição detalhada do problema, escopo e requisitos | Não iniciado |
| **Planejamento** | Setembro | Definição da arquitetura e escolha de bibliotecas/tecnologias | Não iniciado |
| **Dados** | Setembro | Seleção, higienização e preparação das bases de dados | Não iniciado |
| **IA / Detecção** | Outubro | Estudo, seleção e desenvolvimento do modelo de IA/anomalias | Não iniciado |
| **Paralelização** | Outubro | Implementação da distribuição de carga em múltiplos processos | Não iniciado |
| **Backend / API** | Outubro | Desenvolvimento do backend em Python e das rotinas de integração | Não iniciado |
| **Interface** | Outubro | Desenvolvimento da camada visual (Frontend), se aplicável | Não iniciado |
| **Testes** | Novembro | Execução de testes de unidade, integração e benchmarking de CPU | Não iniciado |
| **Validação** | Novembro | Análise dos resultados de desempenho e qualidade da classificação | Não iniciado |
| **Documentação** | Novembro | Consolidação do relatório técnico final do projeto | Não iniciado |
| **Apresentação** | Dezembro | Apresentação e demonstração prática do software desenvolvido | Não iniciado |

---

## 11. Repositório GitHub

O código-fonte, a documentação e os scripts do projeto estarão centralizados no repositório oficial da equipe:

- **Plataforma:** GitHub
- **Repositório:** `transaction-fraud-detector`
- **Link:** https://github.com/MysticXiz/transaction-fraud-detector
- **Organização / Proprietário:** Bruno Severino de Almeida Rocha

---

> **Documento:** Proposta Inicial de Projeto – Sprint 01  
> **Projeto:** Sistema Inteligente de Detecção de Fraudes em Transações
