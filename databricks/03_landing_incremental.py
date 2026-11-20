# Databricks notebook source
# MAGIC %md
# MAGIC # Ingestão incremental: Neon → Landing (CSV)
# MAGIC
# MAGIC Issue #12. Lê as 15 tabelas do esquema `origem` pelo catálogo federado do Neon
# MAGIC e grava em CSV bruto no Volume da Landing.
# MAGIC
# MAGIC **Carga incremental:** toda tabela da origem tem a coluna `atualizado_em`.
# MAGIC A tabela de controle `workspace.amrec.controle_landing` guarda a maior data
# MAGIC já carregada de cada tabela (o *watermark*). Cada execução busca só as linhas
# MAGIC com `atualizado_em` maior que esse valor.
# MAGIC
# MAGIC - Primeira execução: sem watermark, carrega tudo.
# MAGIC - Próximas execuções: só o que foi inserido ou alterado desde a última.
# MAGIC - Tabela sem novidade: nada é gravado.

# COMMAND ----------

from datetime import datetime, timezone

from pyspark.sql import functions as F

CATALOGO_ORIGEM = "neon_origem_catalog"
SCHEMA_ORIGEM = "origem"

CATALOGO = "workspace"
SCHEMA = "amrec"
VOLUME_LANDING = f"/Volumes/{CATALOGO}/{SCHEMA}/landing"
TABELA_CONTROLE = f"{CATALOGO}.{SCHEMA}.controle_landing"

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

# Formato de data e hora com microssegundos e fuso, para o watermark não perder precisão.
FORMATO_TIMESTAMP = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX"

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"run_id: {RUN_ID}")

# COMMAND ----------

# Tabela de controle: uma linha por execução e por tabela.
spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {TABELA_CONTROLE} (
        tabela            STRING    NOT NULL,
        run_id            STRING    NOT NULL,
        watermark_anterior TIMESTAMP,
        watermark_novo    TIMESTAMP,
        linhas            BIGINT    NOT NULL,
        caminho           STRING,
        executado_em      TIMESTAMP NOT NULL
    ) USING DELTA
""")


def ultimo_watermark(tabela):
    """Maior atualizado_em já carregado na Landing para a tabela, ou None."""
    linha = (
        spark.table(TABELA_CONTROLE)
        .where(F.col("tabela") == tabela)
        .agg(F.max("watermark_novo").alias("wm"))
        .first()
    )
    return linha["wm"]

# COMMAND ----------

def ingerir(tabela):
    origem = spark.table(f"{CATALOGO_ORIGEM}.{SCHEMA_ORIGEM}.{tabela}")
    watermark = ultimo_watermark(tabela)

    if watermark is not None:
        origem = origem.where(F.col("atualizado_em") > F.lit(watermark))

    caminho = f"{VOLUME_LANDING}/{tabela}/run_id={RUN_ID}"

    # Landing: CSV bruto, sem regra de negócio.
    (
        origem.write
        .mode("overwrite")
        .option("header", "true")
        .option("timestampFormat", FORMATO_TIMESTAMP)
        .csv(caminho)
    )

    # Conferência: lê de volta o que foi gravado e calcula o novo watermark a partir dele.
    gravado = (
        spark.read
        .option("header", "true")
        .option("timestampFormat", FORMATO_TIMESTAMP)
        .csv(caminho)
        .withColumn("atualizado_em", F.to_timestamp("atualizado_em", FORMATO_TIMESTAMP))
    )
    resumo = gravado.agg(
        F.count(F.lit(1)).alias("linhas"),
        F.max("atualizado_em").alias("wm"),
    ).first()
    linhas = resumo["linhas"]

    if linhas == 0:
        # Sem novidade: remove o diretório vazio e mantém o watermark anterior.
        dbutils.fs.rm(caminho, recurse=True)
        novo_watermark, caminho = watermark, None
    else:
        novo_watermark = resumo["wm"]
        if novo_watermark is None:
            raise ValueError(f"{tabela}: atualizado_em ficou nulo após a leitura do CSV")

    registro = spark.createDataFrame(
        [(tabela, RUN_ID, watermark, novo_watermark, linhas, caminho, datetime.now(timezone.utc))],
        "tabela string, run_id string, watermark_anterior timestamp, "
        "watermark_novo timestamp, linhas bigint, caminho string, executado_em timestamp",
    )
    registro.write.mode("append").saveAsTable(TABELA_CONTROLE)

    print(f"{tabela:<30} {linhas:>10,} linhas  (watermark: {watermark} → {novo_watermark})")
    return linhas

# COMMAND ----------

total = 0
for tabela in TABELAS:
    total += ingerir(tabela)

print(f"\nTotal gravado na Landing nesta execução: {total:,} linhas")

# COMMAND ----------

# Resumo desta execução.
display(
    spark.table(TABELA_CONTROLE)
    .where(F.col("run_id") == RUN_ID)
    .orderBy("tabela")
)
