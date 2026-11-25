# Databricks notebook source
# MAGIC %md
# MAGIC # Gold: fatos e tabelas do dashboard
# MAGIC
# MAGIC Issues #16 e #18. Rode depois do `06_gold_dimensoes`. Grava no schema `workspace.amrec_gold`:
# MAGIC
# MAGIC | Tabela | Grão | Carga |
# MAGIC | --- | --- | --- |
# MAGIC | `fato_empenho` | um empenho | incremental, MERGE por `id_empenho` |
# MAGIC | `fato_populacao` | município × ano | recriada (48 linhas, do IBGE) |
# MAGIC | `agg_empenhado_municipio_ano` | município × ano | recriada; KPIs e gráfico de grupos |
# MAGIC | `agg_empenhado_area` | município × ano × área | recriada; gráfico por área |
# MAGIC
# MAGIC **Empenhado** = valor original do empenho − soma das anulações. Anulações só existem no Betha.
# MAGIC
# MAGIC **Carga incremental do fato:** um empenho precisa ser recalculado quando ele mesmo muda ou quando
# MAGIC recebe uma anulação. A tabela `workspace.amrec.controle_gold` guarda, para cada tabela da Silver lida,
# MAGIC o maior `_processado_silver_em` já aplicado (o watermark). Cada execução recalcula só os empenhos
# MAGIC com linhas mais novas que isso, em `empenho` ou em `anulacao_empenho`.
# MAGIC
# MAGIC **Dimensões no fato:** cada empenho aponta para a versão da dimensão válida na data de emissão
# MAGIC (SCD tipo 2). Sem função ou sem elemento, aponta para o membro `-1` ("Não informada").

# COMMAND ----------

from datetime import datetime, timezone

from delta.tables import DeltaTable
from pyspark.sql import functions as F

CATALOGO = "workspace"
SCHEMA_SILVER = f"{CATALOGO}.amrec_silver"
SCHEMA_GOLD = f"{CATALOGO}.amrec_gold"
VOLUME_REFERENCIA = f"/Volumes/{CATALOGO}/amrec/referencia"
CONTROLE_GOLD = f"{CATALOGO}.amrec.controle_gold"

FATO_EMPENHO = f"{SCHEMA_GOLD}.fato_empenho"
FONTES_FATO_EMPENHO = ["empenho", "anulacao_empenho"]

EXECUCAO_GOLD = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"Execução da Gold: {EXECUCAO_GOLD}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CONTROLE_GOLD} (
        tabela_gold     STRING    NOT NULL,
        tabela_silver   STRING    NOT NULL,
        execucao_gold   STRING    NOT NULL,
        watermark       TIMESTAMP,
        linhas_lidas    BIGINT    NOT NULL,
        processado_em   TIMESTAMP NOT NULL
    ) USING DELTA
""")

# COMMAND ----------

def ultimo_watermark(tabela_gold, tabela_silver):
    linha = (
        spark.table(CONTROLE_GOLD)
        .where((F.col("tabela_gold") == tabela_gold) & (F.col("tabela_silver") == tabela_silver))
        .agg(F.max("watermark").alias("wm"))
        .first()
    )
    return linha["wm"]


def novidades(tabela_silver, watermark):
    """Linhas da Silver processadas depois do watermark (todas, na primeira execução)."""
    dados = spark.table(f"{SCHEMA_SILVER}.{tabela_silver}")
    if watermark is not None:
        dados = dados.where(F.col("_processado_silver_em") > F.lit(watermark))
    return dados


def versao_na_data(fato, dim, chave_fato, chave_dim, sk, data):
    """Junta a versão da dimensão SCD2 válida na data do fato; sem correspondência, sk = -1."""
    d = spark.table(f"{SCHEMA_GOLD}.{dim}").where(F.col(chave_dim).isNotNull()).select(
        F.col(chave_dim).alias(f"_{dim}_chave"), F.col(sk).alias(f"_{dim}_sk"),
        F.col("data_inicio").alias(f"_{dim}_ini"), F.col("data_fim").alias(f"_{dim}_fim"),
    )
    momento = F.col(data).cast("timestamp")
    return (
        fato.join(
            d,
            (F.col(chave_fato) == F.col(f"_{dim}_chave"))
            & (momento >= F.col(f"_{dim}_ini")) & (momento < F.col(f"_{dim}_fim")),
            "left",
        )
        .withColumn(sk, F.coalesce(F.col(f"_{dim}_sk"), F.lit(-1).cast("bigint")))
        .drop(f"_{dim}_chave", f"_{dim}_sk", f"_{dim}_ini", f"_{dim}_fim")
    )

# COMMAND ----------

# MAGIC %md
# MAGIC ## fato_empenho (incremental)

# COMMAND ----------

watermarks = {t: ultimo_watermark("fato_empenho", t) for t in FONTES_FATO_EMPENHO}
lidos = {t: novidades(t, watermarks[t]) for t in FONTES_FATO_EMPENHO}

# Watermark novo e quantidade lida, calculados sobre o que foi lido nesta execução.
resumo_lido = {
    t: df.agg(F.count(F.lit(1)).alias("linhas"), F.max("_processado_silver_em").alias("wm")).first()
    for t, df in lidos.items()
}

ids_alterados = (
    lidos["empenho"].select("id_empenho")
    .union(lidos["anulacao_empenho"].select("id_empenho"))
    .distinct()
)

anulado = (
    spark.table(f"{SCHEMA_SILVER}.anulacao_empenho")
    .join(ids_alterados, "id_empenho", "left_semi")
    .groupBy("id_empenho")
    .agg(F.sum("valor").alias("valor_anulado"))
)

empenhos = (
    spark.table(f"{SCHEMA_SILVER}.empenho")
    .join(ids_alterados, "id_empenho", "left_semi")
    .join(anulado, "id_empenho", "left")
)
empenhos = versao_na_data(empenhos, "dim_municipio", "ibge", "ibge", "sk_municipio", "data_emissao")
empenhos = versao_na_data(empenhos, "dim_funcao", "codigo_funcao", "codigo", "sk_funcao", "data_emissao")
empenhos = versao_na_data(empenhos, "dim_elemento_despesa", "codigo_elemento", "codigo", "sk_elemento", "data_emissao")

fato = empenhos.select(
    "id_empenho",
    F.date_format("data_emissao", "yyyyMMdd").cast("int").alias("sk_data"),
    "sk_municipio",
    "sk_funcao",
    "sk_elemento",
    "ano",
    "entidade",
    "numero",
    "elemento_inferido",
    F.col("valor").alias("valor_original"),
    F.coalesce("valor_anulado", F.lit(0)).cast("decimal(15,2)").alias("valor_anulado"),
    (F.col("valor") - F.coalesce("valor_anulado", F.lit(0))).cast("decimal(15,2)").alias("valor_empenhado"),
    F.current_timestamp().alias("_processado_gold_em"),
)

linhas_fato = fato.count()
if linhas_fato:
    if not spark.catalog.tableExists(FATO_EMPENHO):
        fato.write.format("delta").saveAsTable(FATO_EMPENHO)
    else:
        (
            DeltaTable.forName(spark, FATO_EMPENHO).alias("alvo")
            .merge(fato.alias("novo"), "alvo.id_empenho = novo.id_empenho")
            .whenMatchedUpdateAll()
            .whenNotMatchedInsertAll()
            .execute()
        )

# O controle só é gravado depois do MERGE: se algo falhar antes, a próxima execução relê as mesmas linhas.
spark.createDataFrame(
    [
        ("fato_empenho", t, EXECUCAO_GOLD, resumo_lido[t]["wm"] or watermarks[t],
         resumo_lido[t]["linhas"], datetime.now(timezone.utc))
        for t in FONTES_FATO_EMPENHO
    ],
    "tabela_gold string, tabela_silver string, execucao_gold string, watermark timestamp, "
    "linhas_lidas bigint, processado_em timestamp",
).write.mode("append").saveAsTable(CONTROLE_GOLD)

print(f"fato_empenho: {linhas_fato:,} empenho(s) recalculado(s) "
      f"(lidas: {resumo_lido['empenho']['linhas']:,} de empenho, "
      f"{resumo_lido['anulacao_empenho']['linhas']:,} de anulacao_empenho)")

# COMMAND ----------

# MAGIC %md
# MAGIC ## fato_populacao
# MAGIC
# MAGIC População do IBGE por município e ano (`databricks/referencia/populacao_municipio.csv`, copiado para o
# MAGIC Volume). 2023 usa o Censo 2022, porque o IBGE não publicou estimativa para 2023. O dado é externo e
# MAGIC não passa pelo banco de origem.

# COMMAND ----------

populacao = (
    spark.read.option("header", "true").option("inferSchema", "false")
    .csv(f"{VOLUME_REFERENCIA}/populacao_municipio.csv")
    .select(
        "ibge",
        F.col("ano").cast("smallint").alias("ano"),
        F.col("populacao").cast("int").alias("populacao"),
        "fonte",
    )
)
municipio_atual = (
    spark.table(f"{SCHEMA_GOLD}.dim_municipio").where("registro_atual").select("ibge", "sk_municipio")
)
(
    populacao.join(municipio_atual, "ibge", "left")
    .select("sk_municipio", "ano", "populacao", "fonte")
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{SCHEMA_GOLD}.fato_populacao")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tabelas do dashboard
# MAGIC
# MAGIC A população é somada **uma vez por município e ano**. Se ela ficasse repetida em cada empenho ou em
# MAGIC cada grupo, a soma no dashboard multiplicaria a população e o valor por habitante sairia errado.
# MAGIC
# MAGIC - `agg_empenhado_municipio_ano`: uma linha por município e ano, com o empenhado aberto em colunas.
# MAGIC   Serve aos 4 KPIs e ao gráfico de pessoal, custeio e investimento.
# MAGIC - `agg_empenhado_area`: uma linha por município, ano e área. Serve ao gráfico por área, com filtro.
# MAGIC   Dentro de uma área, cada município e ano aparece uma vez, então a soma da população está certa.
# MAGIC
# MAGIC As duas são pequenas e recriadas a cada execução a partir do fato inteiro.

# COMMAND ----------

dim_municipio = spark.table(f"{SCHEMA_GOLD}.dim_municipio")
nomes_atuais = dim_municipio.where("registro_atual").select("ibge", F.col("nome").alias("municipio"), "fonte")

base = (
    spark.table(FATO_EMPENHO)
    .join(dim_municipio.select("sk_municipio", "ibge"), "sk_municipio")
    .join(spark.table(f"{SCHEMA_GOLD}.dim_funcao").select("sk_funcao", "area"), "sk_funcao")
    .join(spark.table(f"{SCHEMA_GOLD}.dim_elemento_despesa").select("sk_elemento", "grupo_despesa"), "sk_elemento")
)
populacao_ano = populacao.select("ibge", "ano", "populacao")


def soma_se(condicao):
    return F.sum(F.when(condicao, F.col("valor_empenhado")).otherwise(F.lit(0))).cast("decimal(18,2)")


(
    base.groupBy("ibge", "ano")
    .agg(
        F.sum("valor_empenhado").cast("decimal(18,2)").alias("empenhado_total"),
        soma_se(F.col("grupo_despesa") == "Pessoal").alias("empenhado_pessoal"),
        soma_se(F.col("grupo_despesa") == "Custeio").alias("empenhado_custeio"),
        soma_se(F.col("grupo_despesa") == "Investimento").alias("empenhado_investimento"),
        soma_se(F.col("grupo_despesa") == "Outros").alias("empenhado_outros_grupos"),
        soma_se(F.col("area") != "Não informada").alias("empenhado_com_funcao"),
        soma_se(F.col("area") == "Saúde").alias("empenhado_saude"),
        F.count(F.lit(1)).alias("empenhos"),
    )
    .join(populacao_ano, ["ibge", "ano"], "left")
    .join(nomes_atuais, "ibge")
    .select("ibge", "municipio", "fonte", "ano", "populacao", "empenhos", "empenhado_total",
            "empenhado_pessoal", "empenhado_custeio", "empenhado_investimento", "empenhado_outros_grupos",
            "empenhado_com_funcao", "empenhado_saude")
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{SCHEMA_GOLD}.agg_empenhado_municipio_ano")
)

(
    base.groupBy("ibge", "ano", "area")
    .agg(F.sum("valor_empenhado").cast("decimal(18,2)").alias("empenhado"))
    .join(populacao_ano, ["ibge", "ano"], "left")
    .join(nomes_atuais, "ibge")
    .select("ibge", "municipio", "fonte", "ano", "area", "empenhado", "populacao")
    .write.format("delta").mode("overwrite").option("overwriteSchema", "true")
    .saveAsTable(f"{SCHEMA_GOLD}.agg_empenhado_area")
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Conferência
# MAGIC
# MAGIC O fato tem que ter um empenho por empenho da Silver e o mesmo valor total, e as tabelas do dashboard
# MAGIC têm que somar o mesmo que o fato. Se algo não bater, a execução para com erro.

# COMMAND ----------

silver = spark.table(f"{SCHEMA_SILVER}.empenho").agg(
    F.count(F.lit(1)).alias("n"), F.sum("valor").alias("valor")).first()
gold = spark.table(FATO_EMPENHO).agg(
    F.count(F.lit(1)).alias("n"), F.countDistinct("id_empenho").alias("ids"),
    F.sum("valor_original").alias("valor"), F.sum("valor_empenhado").alias("empenhado"),
    F.sum(F.when(F.col("sk_municipio") == -1, 1).otherwise(0)).alias("sem_municipio")).first()
agg_total = spark.table(f"{SCHEMA_GOLD}.agg_empenhado_municipio_ano").agg(F.sum("empenhado_total")).first()[0]
area_total = spark.table(f"{SCHEMA_GOLD}.agg_empenhado_area").agg(F.sum("empenhado")).first()[0]
sem_populacao = spark.table(f"{SCHEMA_GOLD}.agg_empenhado_municipio_ano").where("populacao IS NULL").count()

problemas = []
if gold["n"] != silver["n"] or gold["ids"] != gold["n"]:
    problemas.append(f"fato com {gold['n']} linhas e {gold['ids']} ids; a Silver tem {silver['n']} empenhos")
if gold["valor"] != silver["valor"]:
    problemas.append(f"valor original do fato ({gold['valor']}) difere da Silver ({silver['valor']})")
if gold["sem_municipio"]:
    problemas.append(f"{gold['sem_municipio']} empenho(s) sem município")
if agg_total != gold["empenhado"] or area_total != gold["empenhado"]:
    problemas.append(f"agregados ({agg_total} e {area_total}) diferentes do fato ({gold['empenhado']})")
if sem_populacao:
    problemas.append(f"{sem_populacao} município(s)/ano(s) sem população")
if problemas:
    raise ValueError("Conferência da Gold: " + "; ".join(problemas))

print(f"OK: {gold['n']:,} empenhos, empenhado total R$ {gold['empenhado']:,.2f}")

# Quanto do empenhado ficou sem função ou sem elemento (vai para "Não informada" e "Outros").
display(
    spark.table(FATO_EMPENHO)
    .groupBy()
    .agg(
        F.round(F.sum(F.when(F.col("sk_funcao") == -1, F.col("valor_empenhado"))) / F.sum("valor_empenhado") * 100, 1)
        .alias("pct_sem_funcao"),
        F.round(F.sum(F.when(F.col("sk_elemento") == -1, F.col("valor_empenhado"))) / F.sum("valor_empenhado") * 100, 1)
        .alias("pct_sem_elemento"),
    )
)
