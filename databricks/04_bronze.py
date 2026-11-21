# Databricks notebook source
# MAGIC %md
# MAGIC # Transformação: Landing (CSV) → Bronze (Delta)
# MAGIC
# MAGIC Issue #13. Lê os CSVs da Landing e grava em tabelas Delta no schema
# MAGIC `workspace.amrec_bronze`, uma tabela por tabela da origem.
# MAGIC
# MAGIC **Regras da Bronze:**
# MAGIC - O conteúdo não é alterado: todas as colunas ficam como texto, do jeito que vieram do CSV.
# MAGIC   A tipagem e a limpeza ficam para a Silver.
# MAGIC - Cada linha ganha colunas de controle: `_run_id`, `_arquivo_origem` e `_data_ingestao`.
# MAGIC - Os dados só são acrescentados (*append*), nunca sobrescritos. Assim a Bronze guarda
# MAGIC   o histórico de tudo o que chegou.
# MAGIC
# MAGIC **Carga incremental:** a tabela `workspace.amrec.controle_bronze` registra quais execuções
# MAGIC da Landing (`run_id`) já foram processadas. Cada execução deste notebook processa só as
# MAGIC execuções da Landing que ainda não estão nesse controle.

# COMMAND ----------

from datetime import datetime, timezone

from pyspark.sql import functions as F

CATALOGO = "workspace"
SCHEMA_BRONZE = "amrec_bronze"
CONTROLE_LANDING = f"{CATALOGO}.amrec.controle_landing"
CONTROLE_BRONZE = f"{CATALOGO}.amrec.controle_bronze"

TABELAS = [
    # Domínios e cadastros
    "municipio",
    "funcao",
    "elemento_despesa",
    "credor",
    "material",
    "documento_fiscal",
    # Execução da despesa
    "empenho",
    "item_empenho",
    "empenho_documento_fiscal",
    "anulacao_empenho",
    "liquidacao",
    "retencao",
    "pagamento",
    "diaria",
    "pagamento_extraorcamentario",
]

EXECUCAO_BRONZE = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"Execução da Bronze: {EXECUCAO_BRONZE}")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{SCHEMA_BRONZE}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CONTROLE_BRONZE} (
        tabela           STRING    NOT NULL,
        run_id_landing   STRING    NOT NULL,
        execucao_bronze  STRING    NOT NULL,
        linhas           BIGINT    NOT NULL,
        processado_em    TIMESTAMP NOT NULL
    ) USING DELTA
""")

# COMMAND ----------

def execucoes_pendentes(tabela):
    """Execuções da Landing com arquivo gravado e que ainda não foram para a Bronze."""
    landing = (
        spark.table(CONTROLE_LANDING)
        .where((F.col("tabela") == tabela) & F.col("caminho").isNotNull() & (F.col("linhas") > 0))
        .select("run_id", "caminho")
    )
    processadas = (
        spark.table(CONTROLE_BRONZE)
        .where(F.col("tabela") == tabela)
        .select(F.col("run_id_landing").alias("run_id"))
    )
    pendentes = landing.join(processadas, "run_id", "left_anti").orderBy("run_id")
    return [(linha["run_id"], linha["caminho"]) for linha in pendentes.collect()]


def processar(tabela):
    pendentes = execucoes_pendentes(tabela)
    if not pendentes:
        print(f"{tabela:<30} nada novo na Landing")
        return 0

    destino = f"{CATALOGO}.{SCHEMA_BRONZE}.{tabela}"
    total = 0

    for run_id, caminho in pendentes:
        # Tudo como texto: a Bronze guarda o dado bruto, sem interpretar tipos.
        # multiLine permite textos com quebra de linha (como o histórico do empenho).
        dados = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "false")
            .option("multiLine", "true")
            .csv(caminho)
            .withColumn("_run_id", F.lit(run_id))
            .withColumn("_arquivo_origem", F.col("_metadata.file_path"))
            .withColumn("_data_ingestao", F.current_timestamp())
        )

        (
            dados.write
            .format("delta")
            .mode("append")
            .option("mergeSchema", "true")
            .saveAsTable(destino)
        )

        # Conferência: as linhas gravadas nesta execução devem bater com o controle da Landing.
        linhas = spark.table(destino).where(F.col("_run_id") == run_id).count()
        esperado = (
            spark.table(CONTROLE_LANDING)
            .where((F.col("tabela") == tabela) & (F.col("run_id") == run_id))
            .first()["linhas"]
        )
        if linhas != esperado:
            raise ValueError(
                f"{tabela} run_id={run_id}: Bronze tem {linhas} linhas, a Landing registrou {esperado}"
            )

        spark.createDataFrame(
            [(tabela, run_id, EXECUCAO_BRONZE, linhas, datetime.now(timezone.utc))],
            "tabela string, run_id_landing string, execucao_bronze string, "
            "linhas bigint, processado_em timestamp",
        ).write.mode("append").saveAsTable(CONTROLE_BRONZE)

        print(f"{tabela:<30} run_id={run_id}  {linhas:>10,} linhas")
        total += linhas

    return total

# COMMAND ----------

total = 0
for tabela in TABELAS:
    total += processar(tabela)

print(f"\nTotal gravado na Bronze nesta execução: {total:,} linhas")

# COMMAND ----------

# Resumo desta execução.
display(
    spark.table(CONTROLE_BRONZE)
    .where(F.col("execucao_bronze") == EXECUCAO_BRONZE)
    .orderBy("tabela", "run_id_landing")
)
