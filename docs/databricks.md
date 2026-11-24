# Lakehouse cloud no Databricks

> Implementação da Issue [#48](https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados/issues/48).

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

## Notebooks

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