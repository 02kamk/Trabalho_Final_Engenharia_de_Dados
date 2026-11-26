# Pipeline no Azure com Airflow

> Issues [#59](https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados/issues/59),
> [#60](https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados/issues/60) e
> [#61](https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados/issues/61) (Milestone 8: Infraestrutura na Azure).

O pipeline saiu do Databricks. O data lake fica no **Azure Data Lake Storage Gen2**, e o **Airflow** e o **Spark**
rodam em Docker na VM do grupo (Ubuntu no WSL). Os notebooks do Databricks estão sendo adaptados para scripts Python
em `pipeline/`, com a mesma lógica: esta etapa (Milestone 8) entrega a infraestrutura e a ingestão na **Landing**;
a Bronze, a Silver e a Gold seguem com o grupo.

```text
Neon (origem)  →  VM: Airflow + Spark (Docker)  →  Azure Data Lake Storage Gen2
                  orquestra e processa             container datalake-amrec:
                                                   landing/ bronze/ silver/ gold/ controle/ referencia/
```

## Recursos no Azure

| Recurso | Nome | Configuração |
| --- | --- | --- |
| Grupo de recursos | `rg-amrec` | Brazil South |
| Conta de armazenamento | `amreclakekm` | Standard, LRS, **namespace hierárquico habilitado** (Data Lake Storage Gen2) |
| Container | `datalake-amrec` | Privado |
| Orçamento | alerta mensal | Aviso por e-mail ao atingir 80% |

O namespace hierárquico é o que transforma o armazenamento em Data Lake Storage Gen2, com pastas de verdade, que o
Delta Lake precisa. Ele só pode ser escolhido na criação da conta.

O Spark acessa o lake pelo endereço `abfss://datalake-amrec@amreclakekm.dfs.core.windows.net/<camada>/<tabela>`,
autenticado com a chave de acesso da conta.

## Camadas e pastas no lake

| Pasta | Conteúdo | Situação |
| --- | --- | --- |
| `landing/<tabela>/run_id=<execução>/` | CSV bruto exportado do Neon (`pipeline/03_landing.py`) | ✅ Implementada |
| `controle/controle_landing` | Watermark de cada tabela e linhas de cada execução | ✅ Implementada |
| `bronze/<tabela>` | Delta com o CSV da Landing em texto e colunas de controle (`pipeline/04_bronze.py`) | 🟡 Implementada, ainda não executada no Azure |
| `controle/controle_bronze` | Execuções da Landing já processadas pela Bronze | 🟡 Idem |
| `silver/`, `gold/` | Camadas Delta, com a lógica dos notebooks `databricks/05` a `07` | ⏳ A adaptar (grupo) |
| `referencia/` | Cópias de `databricks/referencia/*.csv`, usadas pela Gold | ⏳ Com a Gold |

O modelo da Gold, as regras de negócio e os indicadores estão em [Camada Gold](gold.md).

### Como a Landing funciona

Toda tabela do Neon tem `atualizado_em`. A tabela `controle/controle_landing` guarda o maior valor já carregado de cada
tabela (o *watermark*). Cada execução consulta no Neon só as linhas com `atualizado_em` maior que esse valor; o filtro
roda no próprio Postgres, então só o que mudou é transferido. Tabela sem novidade não gera arquivo. O script lê de
volta cada CSV gravado para conferir a quantidade de linhas e calcular o novo watermark.

### O que mudou em relação ao Databricks

| No Databricks | Aqui |
| --- | --- |
| Catálogo federado do Neon | Leitura por JDBC, com o filtro `atualizado_em > watermark` executado no próprio Postgres |
| Volume `landing` e tabelas `workspace.amrec_*` | Pastas no Azure Data Lake Storage (`DeltaTable.forPath`) |
| `sk` das dimensões como coluna de identidade | `sk` calculada no código: maior `sk` existente + 1, 2, 3... |
| `dbutils`, `display`, `spark` pronto | Funções de `pipeline/comum.py` (`criar_spark`, `ler`, `gravar`, `apagar`, `mostrar`) |
| Databricks Jobs | DAG `amrec_pipeline` do Airflow |

## Arquivos

| Arquivo | O que é |
| --- | --- |
| `compose.pipeline.yml` | Sobe o Airflow (modo *standalone*) com o Spark, montando `dags/`, `pipeline/` e `databricks/referencia/` |
| `docker/airflow-spark/Dockerfile` | Airflow 3.4 + Java 17 (Eclipse Temurin) + PySpark 3.5.3 + delta-spark 3.2.1 |
| `pipeline/comum.py` | Sessão Spark com Delta e acesso ao Azure, caminhos do lake, leitura do Neon e funções para ler e gravar tabelas Delta no lake (usadas também pelas próximas camadas) |
| `pipeline/00_teste_conexao.py` | Teste de ponta a ponta: lê o Neon, grava, lê e faz MERGE numa tabela Delta em `_teste/` |
| `pipeline/03_landing.py` | Ingestão incremental Neon → Landing |
| `pipeline/04_bronze.py` | Landing → Bronze (Delta, append, só execuções novas) |
| `dags/amrec_pipeline.py` | A DAG do pipeline (tarefas `landing` e `bronze`) |

Os pacotes Java do Spark (Delta, `hadoop-azure` e o driver do PostgreSQL) são baixados do Maven Central na primeira
execução e ficam guardados no volume `spark-ivy`.

O Java vem da imagem oficial Eclipse Temurin, e não do `apt` do Debian: na montagem da imagem, os downloads do `apt`
falharam várias vezes com *Hash Sum mismatch*, e o Temurin já traz os certificados que o Java usa para baixar os
pacotes do Spark por HTTPS.

## Credenciais

Ficam em dois arquivos na raiz do repositório, **fora do Git** (os dois estão no `.gitignore`):

| Arquivo | Variáveis |
| --- | --- |
| `.env` | `AZURE_STORAGE_ACCOUNT`, `AZURE_STORAGE_KEY`, `AZURE_CONTAINER` (modelo em `.env.example`) |
| `.env.neon` | `DATABASE_URL_UNPOOLED` (ver [Banco de origem](banco.md)) |

A chave do Azure fica em **amreclakekm → Segurança + rede → Chaves de acesso**. Se ela for exposta (num print, num
commit ou numa mensagem), gire a chave nessa mesma tela e atualize o `.env`.

## Como rodar

No Ubuntu (WSL), na raiz do repositório:

```bash
cd "/mnt/c/.../Trabalho_Final_Engenharia_de_Dados"

# 1. Montar a imagem e ligar o Airflow (a primeira vez leva alguns minutos)
docker compose -f compose.pipeline.yml up -d --build

# 2. Testar Neon → Spark → Delta → Azure
docker compose -f compose.pipeline.yml exec airflow python /opt/airflow/pipeline/00_teste_conexao.py
```

O teste tem que terminar com `OK: Neon, Spark, Delta e Azure Data Lake Storage funcionando juntos.`

Depois de alterar o `.env` ou o `.env.neon`, recrie o contêiner para ele ler os arquivos de novo:
`docker compose -f compose.pipeline.yml up -d --force-recreate`.

### Airflow

O painel fica em <http://localhost:8080>, com o usuário `admin`. A senha é gerada pelo próprio Airflow:

```bash
docker compose -f compose.pipeline.yml exec airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

A DAG `amrec_pipeline` tem, por enquanto, a tarefa `landing`. As próximas camadas entram na lista `ETAPAS` do arquivo
`dags/amrec_pipeline.py`, na ordem de execução, conforme forem adaptadas:

```text
landing → bronze → silver → gold_dimensoes → gold_fatos
```

| Configuração | Valor | Motivo |
| --- | --- | --- |
| Agendamento | Todo dia às 06:00 (America/Sao_Paulo) | A origem muda pouco, e a carga incremental lê só o que mudou |
| Execuções simultâneas | 1 | Duas execuções juntas leriam e gravariam os mesmos watermarks |
| Novas tentativas | Nenhuma | Uma falha indica um problema a corrigir. Depois de corrigir, basta rodar de novo: cada camada só grava o controle depois da carga, e a Silver e a Gold usam MERGE |

Para rodar manualmente, ligue a chave da `amrec_pipeline` e clique em **▶ Trigger**. O agendamento só funciona
enquanto o contêiner estiver ligado.

A primeira execução traz o Neon inteiro (3,4 milhões de linhas, cerca de 0,5 GB da cota mensal de transferência do
Neon). As seguintes leem só as linhas com `atualizado_em` maior que o watermark de cada tabela.

## Validação

- **Teste de conexão (25/11/2026):** `00_teste_conexao.py` leu os 12 municípios do Neon, gravou a tabela Delta em
  `_teste/municipio` no Azure, fez um MERGE e terminou com `OK`.
- **Primeira carga da Landing pela DAG (25/11/2026):** **3.447.345 linhas** nas 15 tabelas, conferidas pela soma de
  `controle/controle_landing`. O total é igual ao do [`docs/validacao.md`](validacao.md), tabela por tabela. A tarefa
  foi interrompida uma vez (o contêiner foi recriado no meio da carga) e retomada pelo Airflow: as tabelas já
  gravadas não foram repetidas, porque cada uma só entra no controle depois de conferida.
- **Reexecução sem mudanças na origem:** 0 linhas gravadas (carga incremental).


## Bronze: como executar no Azure

O `pipeline/04_bronze.py` adapta o `databricks/04_bronze.py` (issue #13). Ele foi escrito e revisado, mas **ainda não foi
executado contra o Azure**: quem tem a chave de acesso da conta deve fazer o roteiro abaixo antes de dar a etapa como
validada.

**Pré-requisitos:** os arquivos `.env` e `.env.neon` preenchidos (ver [Credenciais](#credenciais)) e a Landing já
carregada, ou seja, `controle/controle_landing` com linhas.

```bash
cd "/mnt/c/.../Trabalho_Final_Engenharia_de_Dados"
git checkout feat/bronze-azure   # ou main, depois do merge

# 1. Garantir que o contêiner está ligado e com o código atual
docker compose -f compose.pipeline.yml up -d --build

# 2. Se a Landing ainda não foi carregada
docker compose -f compose.pipeline.yml exec airflow python /opt/airflow/pipeline/03_landing.py

# 3. Rodar a Bronze
docker compose -f compose.pipeline.yml exec airflow python /opt/airflow/pipeline/04_bronze.py
```

Também dá para acionar a DAG `amrec_pipeline` no Airflow: a tarefa `bronze` roda depois da `landing`.

**Como conferir o resultado**

1. No fim do log, a tabela `controle_bronze` lista uma linha por tabela e execução da Landing.
2. O total de linhas da Bronze deve ser igual à soma de `linhas` em `controle/controle_landing` (3.447.345 na primeira carga).
3. No portal do Azure, em **amreclakekm → Contêineres → datalake-amrec**, devem existir as pastas `bronze/<tabela>` (15) e
   `controle/controle_bronze`, cada uma com uma subpasta `_delta_log`.
4. Uma segunda execução, sem nada novo na Landing, deve imprimir `nada novo na Landing` em todas as tabelas.

**Se algo falhar:** o controle só é gravado depois da conferência de linhas, então basta corrigir e rodar de novo. Se a
execução tiver gravado parte da Bronze antes de falhar, o script apaga as linhas daquele `run_id` antes de gravar outra vez,
e nada fica duplicado.
