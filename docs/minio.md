# Data lake no MinIO

!!! note "MVP local substituído"
    Esta página documenta o primeiro MVP do data lake, local, com MinIO e Airflow. O projeto migrou para o Databricks Free Edition (issue #48), descrito em [Lakehouse no Databricks](databricks.md). O MVP fica registrado aqui até a homologação da arquitetura cloud.

O Trabalho Final usa o bucket privado `datalake-amrec` no MinIO. Cada camada tem um prefixo na raiz do bucket.

| Prefixo | Formato | Conteúdo |
| --- | --- | --- |
| `landing/` | CSV | Exportações do esquema `origem` no PostgreSQL do Neon |
| `bronze/` | Delta Lake | Dados da Landing com informações de controle da ingestão |
| `silver/` | Delta Lake | Dados tipados e tratados |
| `gold/` | Delta Lake | Modelo para consumo pelo dashboard |

## Conexão

No Ubuntu WSL2 que hospeda o contêiner `minio-ed`, a API S3 responde em `http://127.0.0.1:9000` e o console em `http://localhost:9001`. O contêiner usa o volume Docker `minio-ed-data`, montado em `/data`.

Para o acesso remoto, o host encaminha a porta TCP `19000` da rede privada Tailscale para a API S3. O responsável pelo ambiente fornece o endereço privado e uma credencial MinIO com acesso ao bucket. O computador que hospeda o contêiner precisa estar ligado, com o Tailscale e o MinIO ativos.

Use o [`.env.example`](https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados/blob/main/.env.example) como referência para a configuração do cliente. Mantenha as credenciais em um arquivo local fora do Git. Para consultar a origem, use a URL direta do Neon descrita em [Banco de origem](banco.md).

## Validação inicial

- A API respondeu `HTTP 200` no Ubuntu e pelo endereço Tailscale no computador que hospeda o MinIO.
- O cliente Python autenticou, listou o bucket e gravou um CSV de teste em `landing/_teste/`.
- A exportação manual de `origem.municipio` gerou `landing/municipio/municipio.csv`, com 12 linhas de dados, conforme a contagem no Neon.
- Os prefixos `bronze/`, `silver/` e `gold/` aparecem no console. As tabelas Delta serão gravadas pelo Spark nas etapas seguintes.
- O teste de acesso a partir da rede de um colega está pendente.

## Ingestão piloto pelo Airflow

O arquivo `compose.airflow.yml` sobe o Airflow Standalone para desenvolvimento. No Ubuntu que hospeda o MinIO, conecte o contêiner `minio-ed` à rede Docker `amrec-pipeline` antes de iniciar o Airflow.

```bash
docker network create amrec-pipeline
docker network connect amrec-pipeline minio-ed
docker compose -f compose.airflow.yml up -d
```

Se a rede já existir e o `minio-ed` já estiver conectado, basta o último comando. O painel fica em `http://127.0.0.1:8080`.

Cadastre estas conexões no Airflow com as credenciais do ambiente:

| ID | Tipo | Parâmetros |
| --- | --- | --- |
| `neon_origem` | Postgres | URL direta do Neon, usando o banco e os parâmetros TLS indicados na URL |
| `minio_amrec` | Amazon Web Services | `endpoint_url` igual a `http://minio-ed:9000`, `region_name` igual a `us-east-1` e `config_kwargs` igual a `{"s3": {"addressing_style": "path"}}` |

No painel, acione a DAG `amrec_landing_municipio`. Ela consulta `origem.municipio`, exporta um CSV com cabeçalho e verifica o conteúdo após gravá-lo em `landing/municipio/execucao-<id>.csv`. Cada execução tem seu próprio caminho.

Em 18/11/2026, a tarefa `exportar_municipio` terminou com sucesso e registrou a verificação de **12 linhas** no CSV gravado. A DAG piloto é acionada manualmente. A expansão para as outras tabelas, a carga incremental e o agendamento seguem no pipeline do projeto.
