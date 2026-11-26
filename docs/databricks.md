# Lakehouse cloud no Databricks

> Implementação da Issue [#48](https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados/issues/48).

!!! note "Arquitetura substituída"
    O pipeline saiu do Databricks e passou a rodar com Airflow e Spark na VM do grupo, com o data lake no Azure
    Data Lake Storage (Milestone 8). Ver [Pipeline no Azure com Airflow](azure.md). Esta página fica como registro
    da etapa anterior; os notebooks continuam em `databricks/`.

## Decisão de arquitetura

O projeto iniciou um MVP local com Airflow e MinIO. Para reduzir dependência da máquina pessoal e permitir a continuidade do trabalho em cloud, a arquitetura do Lakehouse está sendo migrada para o Databricks Free Edition.

O MinIO local não está integrado ao Databricks. Ele permanece temporariamente como evidência do MVP anterior e não deve ser removido até a homologação completa da arquitetura cloud pelo grupo e pelo professor.

## Fluxo

```text
Neon PostgreSQL
  ↓ catálogo federado
neon_origem_catalog.origem
  ↓ ingestão CSV bruto
Volume workspace.amrec.landing
  ↓ Delta Lake
workspace.amrec_bronze
  ↓ Delta Lake
workspace.amrec_silver
  ↓ Delta Lake
workspace.amrec_gold
```

## Conexão com a origem

No Databricks foi criada a conexão `neon_origem`, do tipo PostgreSQL, e o catálogo federado `neon_origem_catalog`. A origem é consultada pelo caminho `neon_origem_catalog.origem.municipio`.

A autenticação foi validada com uma consulta que retornou os 12 municípios. As credenciais ficam na conexão governada do Databricks; não devem ser incluídas em notebooks, arquivos versionados ou na documentação.

## Landing

Foi criado o Volume `workspace.amrec.landing`. A carga-piloto leu `origem.municipio` do Neon e gravou um CSV bruto no caminho:

```text
/Volumes/workspace/amrec/landing/municipio/run_id=<identificador>
```

A leitura do arquivo após a gravação confirmou os mesmos 12 registros da origem.

## Teste Delta na Bronze

O notebook `02` confirma que o workspace grava e lê tabelas Delta em `workspace.amrec_bronze`. Ele grava a tabela temporária `_teste_delta`, verifica com `DESCRIBE DETAIL` que o formato é `delta`, compara as contagens da origem, da Landing e da tabela Delta, mostra o `DESCRIBE HISTORY` e apaga a tabela ao final.

## Ingestão incremental para a Landing

O notebook `03` lê as 15 tabelas pelo catálogo federado e grava cada uma em CSV no caminho:

```text
/Volumes/workspace/amrec/landing/<tabela>/run_id=<data e hora UTC>
```

O controle é feito pela coluna `atualizado_em`, presente em todas as tabelas da origem, e pela tabela Delta `workspace.amrec.controle_landing`, que registra uma linha por tabela e por execução:

| Coluna | Conteúdo |
| --- | --- |
| `tabela` | tabela da origem |
| `run_id` | identificador da execução |
| `watermark_anterior` / `watermark_novo` | maior `atualizado_em` carregado antes e depois da execução |
| `linhas` | linhas gravadas na execução |
| `caminho` | diretório do CSV na Landing (nulo quando não houve novidade) |
| `executado_em` | data e hora da execução |

- **Primeira execução:** sem watermark, carrega a tabela inteira.
- **Execuções seguintes:** só as linhas com `atualizado_em` maior que o último watermark.
- **Sem novidade:** o diretório vazio é removido e o watermark se mantém.

O novo watermark é calculado a partir do CSV lido de volta, e não da consulta à origem, para garantir que só avança sobre o que de fato foi gravado.

!!! warning "Recarga completa da origem"
    O `sql/origem.sql` apaga e recria o esquema `origem`. Depois de uma recarga, todas as linhas recebem um `atualizado_em` novo, e a execução seguinte do notebook `03` grava as 15 tabelas inteiras de novo (cerca de 0,5 GB de transferência no Neon). Exclusões na origem também não chegam à Landing, porque a linha some em vez de ser marcada.

## Notebooks

Os notebooks ficam em `databricks/`, no formato de código-fonte do Databricks. O `01_piloto_landing_municipio.py`
(#48) e o `02_teste_delta_bronze.py` (#11) foram o piloto da migração, descrito acima; o pipeline roda do `03` ao
`07`, em ordem:

| Camada | Notebook | Destino |
| --- | --- | --- |
| Landing | `databricks/03_landing_incremental.py` | Volume `workspace.amrec.landing` (controle `workspace.amrec.controle_landing`) |
| Bronze | `databricks/04_bronze.py` | `workspace.amrec_bronze` (controle `workspace.amrec.controle_bronze`) |
| Silver | `databricks/05_silver.py` | `workspace.amrec_silver` (controle `workspace.amrec.controle_silver`) |
| Gold | `databricks/06_gold_dimensoes.py` e `databricks/07_gold_fatos.py` | `workspace.amrec_gold` (controle `workspace.amrec.controle_gold`); ver [Camada Gold](gold.md) |

## Próximas etapas

- Gerar o `elemento_grupo.csv` definitivo a partir dos brutos do Betha (ver [Camada Gold](gold.md)).
- Montar o dashboard a partir das tabelas `agg_` da Gold.
- Configurar a execução agendada no Databricks Jobs/Workflows.
- Validar a arquitetura cloud com o grupo e o professor antes de descontinuar o MVP local.