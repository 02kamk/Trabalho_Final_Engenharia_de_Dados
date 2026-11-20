# Databricks notebook source
# MAGIC %md
# MAGIC # Teste: escrita e leitura de tabela Delta na Bronze
# MAGIC
# MAGIC Confere que o workspace grava e lê tabelas Delta no schema `amrec_bronze`.
# MAGIC Lê o CSV de `municipio` da Landing (piloto), grava como Delta, lê de volta,
# MAGIC compara com a origem e remove a tabela de teste.

# COMMAND ----------

CATALOGO = "workspace"
SCHEMA_BRONZE = "amrec_bronze"
TABELA_ORIGEM = "neon_origem_catalog.origem.municipio"
TABELA_TESTE = f"{CATALOGO}.{SCHEMA_BRONZE}._teste_delta"
LANDING_MUNICIPIO = f"/Volumes/{CATALOGO}/amrec/landing/municipio"

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{SCHEMA_BRONZE}")

# COMMAND ----------

# Lê todos os CSVs da Landing (um diretório run_id=... por execução do piloto).
# Usa apenas a execução mais recente, para não contar linhas repetidas.
execucoes = sorted(
    arquivo.name for arquivo in dbutils.fs.ls(LANDING_MUNICIPIO) if arquivo.isDir()
)
if not execucoes:
    raise ValueError(f"Nenhuma execução em {LANDING_MUNICIPIO}; rode o notebook 01 antes")

ultima_execucao = f"{LANDING_MUNICIPIO}/{execucoes[-1]}"
landing = spark.read.option("header", "true").csv(ultima_execucao)
linhas_landing = landing.count()

# COMMAND ----------

# Escrita Delta e leitura de volta.
(
    landing.write
    .format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(TABELA_TESTE)
)

delta = spark.table(TABELA_TESTE)
linhas_delta = delta.count()

# O formato da tabela precisa ser Delta, e não apenas a escrita ter funcionado.
formato = spark.sql(f"DESCRIBE DETAIL {TABELA_TESTE}").first()["format"]
if formato != "delta":
    raise ValueError(f"Formato inesperado para {TABELA_TESTE}: {formato}")

# COMMAND ----------

# Conferência: Landing, Delta e origem federada no Neon têm a mesma contagem.
linhas_origem = spark.table(TABELA_ORIGEM).count()

if not (linhas_origem == linhas_landing == linhas_delta):
    raise ValueError(
        f"Contagens diferentes: origem={linhas_origem}, "
        f"landing={linhas_landing}, delta={linhas_delta}"
    )

# Histórico do Delta: confirma que houve uma escrita registrada no log de transações.
spark.sql(f"DESCRIBE HISTORY {TABELA_TESTE}").select(
    "version", "operation", "operationMetrics"
).show(truncate=False)

# COMMAND ----------

# Remove a tabela de teste para não deixar lixo na Bronze.
spark.sql(f"DROP TABLE IF EXISTS {TABELA_TESTE}")

print(f"Formato: {formato}")
print(f"Linhas: origem={linhas_origem}, landing={linhas_landing}, delta={linhas_delta}")
print(f"OK: tabela Delta gravada e lida em {TABELA_TESTE} (removida ao final)")
