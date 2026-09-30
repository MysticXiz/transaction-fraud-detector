# SISTEMA INTELIGENTE DE DETECÇÃO DE FRAUDES EM TRANSAÇÕES
## Documento Técnico — Sprint 03
### Implementação, Persistência e Controle de Acesso

**Curso:** Ciência da Computação — **Turma:** 8MB — **Instituição:** UNINASSAU
**Disciplinas:** Fábrica de Software / Tópicos Avançados em Ciência da Computação
**Professores:** Pryscilla de Barros Gonçalves; Antenor Jorge Parnaiba da Silva

**Equipe:** Bruno Severino de Almeida Rocha; Rodrigo Amorim Neves; Everson Padilha Ferreira; Eduardo Barros Magalhães

**Repositório:** https://github.com/MysticXiz/transaction-fraud-detector

---

## 1. Estrutura implementada

A Sprint 03 consolidou a organização do backend em camadas, separando a API, a aplicação, o domínio e a infraestrutura. A estrutura foi organizada para manter responsabilidades bem definidas entre rotas, casos de uso, entidades e persistência em banco de dados.

A aplicação passou a contar com:

- API em FastAPI;
- integração com PostgreSQL via SQLAlchemy;
- autenticação com JWT;
- controle de acesso por perfil de usuário;
- CRUD de transações persistido em banco.

---

## 2. Evidências do banco de dados conectado
#### Banco de dados em execução;
![alt text](termsnap.png)
#### Tabela de usuários ou registros persistidos.
![alt text](image-6.png)


---

## 3. Evidências de login, cadastro e controle de perfis
#### Evidência de login com sucesso em `POST /auth/login`;
![alt text](image-5.png)
#### Evidência de cadastro realizado por usuário com perfil ADMIN em `POST /auth/register`;
![alt text](image-2.png)
#### Evidência de bloqueio para usuário ANALISTA em `POST /auth/register` com retorno `403 Forbidden`;
![alt text](image-3.png)
#### Evidência de acesso ao perfil autenticado em `GET /auth/me`.
![alt text](image-4.png)

Login, criação de usuário, consulta e restrições funcionando corretamente.

---

## 4. Evidências do CRUD principal funcionando



#### Criação de transação em `POST /transactions` com retorno `201 Created`;
![alt text](image-7.png)
#### Listagem de transações em `GET /transactions` com retorno `200 OK`;
![alt text](image-8.png)
#### Atualização em `PATCH /transactions/{id}` com retorno `200 OK`;
![alt text](image-9.png)
#### Exclusão em `DELETE /transactions/{id}` com retorno `204 No Content`.
![alt text](image-10.png)

Operações de CRUD da entidade Transação funcionando corretamente.

---

## 5. Procedimento de execução local

Para executar o projeto localmente, é necessário:

1. Clonar o repositório;
2. Criar e ativar o ambiente virtual;
3. Instalar as dependências com `pip install -r backend/requirements.txt`;
4. Configurar as variáveis de ambiente do projeto, incluindo a conexão com o PostgreSQL e o segredo JWT;
5. Iniciar o banco com `docker compose up -d`;
6. Executar a API com o comando correto do projeto.

Exemplo de comando de execução da API:

```powershell
uvicorn src.fraud_detector.main:app --reload
```

A documentação interativa da API pode ser acessada em:

```text
http://localhost:8000/docs
```

---

## 6. Dificuldades encontradas e próximos passos

Durante a Sprint 03, as principais dificuldades estiveram relacionadas à organização das camadas da arquitetura.

Também foi necessário ajustar a separação de responsabilidades entre rotas e casos de uso, além de alinhar os modelos SQLAlchemy com o banco de dados já definido.

Como próximos passos, a equipe deve continuar com:

- ingestão e validação dos datasets;
- pré-processamento dos dados;
- implementação dos algoritmos de detecção de fraude;
- execução sequencial e paralela dos algoritmos;
- persistência dos resultados de análise;
- coleta de métricas e benchmarks;
- evolução da interface e consolidação de migrações.

---

