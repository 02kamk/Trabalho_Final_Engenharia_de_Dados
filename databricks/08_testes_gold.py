# Databricks notebook source
# MAGIC %md
# MAGIC # Testes da camada Gold
# MAGIC
# MAGIC Issue #55. Rode depois do `07_gold_fatos`. Confere se as camadas rodaram até o fim e se a Gold está
# MAGIC correta. No Job do pipeline (issue #19), é a última tarefa antes do dashboard.
# MAGIC
# MAGIC O notebook só lê as tabelas. Cada teste conta as linhas com problema e vira uma linha no resultado:
# MAGIC
# MAGIC | Situação | Quando |
# MAGIC | --- | --- |
# MAGIC | `OK` | Nenhuma linha com problema |
# MAGIC | `FALHOU` | Erro no pipeline ou na Gold. No fim, a execução para com erro |
# MAGIC | `AVISO` | Característica dos dados, e não erro do pipeline. Não para a execução |
# MAGIC
# MAGIC Os grupos de teste estão descritos em `docs/gold.md`.

# COMMAND ----------

from pyspark.sql import Window
from pyspark.sql import functions as F

CATALOGO = "workspace"
SCHEMA_SILVER = f"{CATALOGO}.amrec_silver"
SCHEMA_GOLD = f"{CATALOGO}.amrec_gold"
CONTROLE_LANDING = f"{CATALOGO}.amrec.controle_landing"
CONTROLE_BRONZE = f"{CATALOGO}.amrec.controle_bronze"
CONTROLE_SILVER = f"{CATALOGO}.amrec.controle_silver"
CONTROLE_GOLD = f"{CATALOGO}.amrec.controle_gold"

# Mesmos limites de validade do 06_gold_dimensoes.
INICIO_VALIDADE = "1900-01-01 00:00:00"
FIM_VALIDADE = "9999-12-31 00:00:00"
inicio_validade = F.to_timestamp(F.lit(INICIO_VALIDADE))
fim_validade = F.to_timestamp(F.lit(FIM_VALIDADE))

# Municípios do Atende.net (Treviso e Morro da Fumaça): não publicam função nem anulações.
ATENDE_NET = ["4218350", "4211207"]

AREAS = ["Administração", "Saúde", "Educação", "Urbanismo", "Outras", "Não informada"]
GRUPOS = ["Pessoal", "Custeio", "Investimento", "Outros"]

resultados = []


def registrar(grupo, teste, problemas, aviso=False):
    """Guarda o resultado de um teste. `problemas` é a quantidade de linhas com problema."""
    if problemas == 0:
        situacao = "OK"
    else:
        situacao = "AVISO" if aviso else "FALHOU"
    resultados.append((grupo, teste, situacao, problemas))
    print(f"{situacao:<7} {grupo:<12} {teste:<62} {problemas:>8,}")


def repetidas(df, colunas):
    """Linhas a mais do que chaves distintas (0 = a chave é única)."""
    return df.count() - df.select(*colunas).distinct().count()

# COMMAND ----------

# MAGIC %md
# MAGIC ## Pipeline
# MAGIC
# MAGIC As tabelas de controle mostram se cada execução passou por todas as camadas. Uma execução da Landing que
# MAGIC não aparece no controle da Bronze ou da Silver indica que um notebook falhou ou não foi rodado.

# COMMAND ----------

landing = (
    spark.table(CONTROLE_LANDING)
    .where(F.col("caminho").isNotNull() & (F.col("linhas") > 0))
    .select("tabela", "run_id")
    .distinct()
)
bronze = spark.table(CONTROLE_BRONZE).select("tabela", F.col("run_id_landing").alias("run_id")).distinct()
silver = spark.table(CONTROLE_SILVER).select("tabela", F.col("run_id_landing").alias("run_id")).distinct()

registrar("Pipeline", "execuções da Landing que não chegaram à Bronze",
          landing.join(bronze, ["tabela", "run_id"], "left_anti").count())
registrar("Pipeline", "execuções da Bronze que não chegaram à Silver",
          bronze.join(silver, ["tabela", "run_id"], "left_anti").count())

# A Gold tem que ter lido tudo o que a Silver processou (watermark da controle_gold).
for tabela in ["empenho", "anulacao_empenho"]:
    watermark = (
        spark.table(CONTROLE_GOLD)
        .where((F.col("tabela_gold") == "fato_empenho") & (F.col("tabela_silver") == tabela))
        .agg(F.max("watermark"))
        .first()[0]
    )
    pendentes = spark.table(f"{SCHEMA_SILVER}.{tabela}")
    if watermark is not None:
        pendentes = pendentes.where(F.col("_processado_silver_em") > F.lit(watermark))
    registrar("Pipeline", f"linhas de {tabela} na Silver que a Gold não leu", pendentes.count())

# As tabelas da Silver lidas pela Gold precisam ter uma linha por chave.
CHAVES_SILVER = {
    "municipio": ["ibge"],
    "funcao": ["codigo"],
    "elemento_despesa": ["codigo"],
    "empenho": ["id_empenho"],
    "anulacao_empenho": ["id_empenho", "sequencia"],
}
for tabela, chave in CHAVES_SILVER.items():
    registrar("Pipeline", f"chaves repetidas em silver.{tabela}",
              repetidas(spark.table(f"{SCHEMA_SILVER}.{tabela}"), chave))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Estrutura
# MAGIC
# MAGIC As 8 tabelas da Gold têm que existir com as colunas do modelo (`docs/gold.md`).

# COMMAND ----------

COLUNAS_SCD = ["data_inicio", "data_fim", "registro_atual", "hash_atributos"]

COLUNAS_GOLD = {
    "dim_municipio": ["sk_municipio", "ibge", "nome", "fonte", "data_coleta", *COLUNAS_SCD],
    "dim_funcao": ["sk_funcao", "codigo", "nome", "area", *COLUNAS_SCD],
    "dim_elemento_despesa": ["sk_elemento", "codigo", "nome", "grupo_despesa", *COLUNAS_SCD],
    "dim_data": ["sk_data", "data", "ano", "trimestre", "mes", "ano_mes"],
    "fato_empenho": [
        "id_empenho", "sk_data", "sk_municipio", "sk_funcao", "sk_elemento", "ano", "entidade", "numero",
        "elemento_inferido", "valor_original", "valor_anulado", "valor_empenhado", "_processado_gold_em",
    ],
    "fato_populacao": ["sk_municipio", "ano", "populacao", "fonte"],
    "agg_empenhado_municipio_ano": [
        "ibge", "municipio", "fonte", "ano", "populacao", "empenhos", "empenhado_total", "empenhado_pessoal",
        "empenhado_custeio", "empenhado_investimento", "empenhado_outros_grupos", "empenhado_com_funcao",
        "empenhado_saude",
    ],
    "agg_empenhado_area": ["ibge", "municipio", "fonte", "ano", "area", "empenhado", "populacao"],
}

for tabela, colunas in COLUNAS_GOLD.items():
    existentes = spark.table(f"{SCHEMA_GOLD}.{tabela}").columns
    faltando = [c for c in colunas if c not in existentes]
    if faltando:
        print(f"{tabela}: faltam as colunas {faltando}")
    registrar("Estrutura", f"colunas faltando em {tabela}", len(faltando))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Dimensões
# MAGIC
# MAGIC Nas dimensões com SCD tipo 2, as versões de cada chave formam uma linha do tempo: a primeira começa em
# MAGIC 1900-01-01, cada versão começa onde a anterior terminou e a última (a atual) vai até 9999-12-31. Assim,
# MAGIC qualquer data de emissão encontra exatamente uma versão.

# COMMAND ----------

# dimensão: (chave natural, chave substituta, tabela da Silver, atributos que vêm da Silver)
DIMENSOES = {
    "dim_municipio": ("ibge", "sk_municipio", "municipio", ["nome", "fonte", "data_coleta"]),
    "dim_funcao": ("codigo", "sk_funcao", "funcao", ["nome"]),
    "dim_elemento_despesa": ("codigo", "sk_elemento", "elemento_despesa", ["nome"]),
}

for dim, (chave, sk, tabela_silver, atributos) in DIMENSOES.items():
    tabela = spark.table(f"{SCHEMA_GOLD}.{dim}")
    versoes = tabela.where(F.col(chave).isNotNull())  # sem o membro -1

    registrar("Dimensões", f"{sk} repetida", repetidas(tabela, [sk]))

    atuais_por_chave = versoes.groupBy(chave).agg(F.sum(F.col("registro_atual").cast("int")).alias("atuais"))
    registrar("Dimensões", f"{dim}: chaves sem exatamente uma versão atual",
              atuais_por_chave.where("atuais <> 1").count())

    janela = Window.partitionBy(chave).orderBy("data_inicio")
    linha_do_tempo = (
        versoes
        .withColumn("fim_anterior", F.lag("data_fim").over(janela))
        .withColumn("proximo_inicio", F.lead("data_inicio").over(janela))
    )
    fora = linha_do_tempo.where(
        (F.col("data_inicio") >= F.col("data_fim"))
        | (F.col("fim_anterior").isNull() & (F.col("data_inicio") != inicio_validade))
        | (F.col("fim_anterior").isNotNull() & (F.col("data_inicio") != F.col("fim_anterior")))
        | (F.col("proximo_inicio").isNull() & (F.col("data_fim") != fim_validade))
        | (F.col("registro_atual") != (F.col("data_fim") == fim_validade))
    ).count()
    registrar("Dimensões", f"{dim}: versões fora da linha do tempo", fora)

    # A versão atual de cada chave tem que ter os mesmos atributos da Silver.
    atual = versoes.where("registro_atual").select(chave, *atributos)
    origem = spark.table(f"{SCHEMA_SILVER}.{tabela_silver}").select(chave, *atributos)
    registrar("Dimensões", f"{dim}: versão atual diferente da Silver",
              atual.exceptAll(origem).count() + origem.exceptAll(atual).count())

municipios_atuais = spark.table(f"{SCHEMA_GOLD}.dim_municipio").where("registro_atual").count()
registrar("Dimensões", "dim_municipio: diferença para os 12 municípios", abs(municipios_atuais - 12))

for dim, sk in [("dim_funcao", "sk_funcao"), ("dim_elemento_despesa", "sk_elemento")]:
    membros = spark.table(f"{SCHEMA_GOLD}.{dim}").where(F.col(sk) == -1).count()
    registrar("Dimensões", f"{dim}: membro -1 faltando ou repetido", abs(membros - 1))

registrar("Dimensões", "dim_funcao: área fora da lista",
          spark.table(f"{SCHEMA_GOLD}.dim_funcao").where(F.col("area").isNull() | ~F.col("area").isin(AREAS))
          .count())
registrar("Dimensões", "dim_elemento_despesa: grupo fora da lista",
          spark.table(f"{SCHEMA_GOLD}.dim_elemento_despesa")
          .where(F.col("grupo_despesa").isNull() | ~F.col("grupo_despesa").isin(GRUPOS))
          .count())

# dim_data: todos os dias de 2023 a 2026, um por linha, com sk_data = yyyymmdd.
dim_data = spark.table(f"{SCHEMA_GOLD}.dim_data")
dias = spark.sql("SELECT explode(sequence(DATE'2023-01-01', DATE'2026-12-31', INTERVAL 1 DAY)) AS data")
registrar("Dimensões", "dim_data: dias faltando, a mais ou repetidos",
          dias.join(dim_data, "data", "left_anti").count()
          + dim_data.join(dias, "data", "left_anti").count()
          + repetidas(dim_data, ["data"]))
registrar("Dimensões", "dim_data: sk_data diferente da data",
          dim_data.where(F.col("sk_data") != F.date_format("data", "yyyyMMdd").cast("int")).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## fato_empenho
# MAGIC
# MAGIC Cada empenho do fato é comparado com o que está na Silver: valores, anulações, data e a versão da
# MAGIC dimensão para a qual ele aponta.

# COMMAND ----------

fato = spark.table(f"{SCHEMA_GOLD}.fato_empenho")
empenho = spark.table(f"{SCHEMA_SILVER}.empenho")
anulado = (
    spark.table(f"{SCHEMA_SILVER}.anulacao_empenho")
    .groupBy("id_empenho")
    .agg(F.sum("valor").alias("anulado_silver"))
)
comparado = (
    fato.join(
        empenho.select("id_empenho", "ibge", "codigo_funcao", "codigo_elemento", "data_emissao", "valor"),
        "id_empenho",
    )
    .join(anulado, "id_empenho", "left")
)

registrar("Fato", "id_empenho repetido", repetidas(fato, ["id_empenho"]))
registrar("Fato", "empenhos da Silver que não estão no fato", empenho.join(fato, "id_empenho", "left_anti").count())
registrar("Fato", "empenhos do fato que não estão na Silver", fato.join(empenho, "id_empenho", "left_anti").count())
registrar("Fato", "valor original diferente da Silver",
          comparado.where(F.col("valor_original") != F.col("valor")).count())
registrar("Fato", "valor anulado diferente da Silver",
          comparado.where(F.col("valor_anulado") != F.coalesce(F.col("anulado_silver"), F.lit(0))).count())
registrar("Fato", "empenhado diferente de original − anulado",
          fato.where(F.col("valor_empenhado") != F.col("valor_original") - F.col("valor_anulado")).count())
registrar("Fato", "sk_data diferente da data de emissão",
          comparado.where(F.col("sk_data") != F.date_format("data_emissao", "yyyyMMdd").cast("int")).count())

algum_nulo = F.lit(False)
for coluna in ["id_empenho", "sk_data", "sk_municipio", "sk_funcao", "sk_elemento", "ano",
               "valor_original", "valor_anulado", "valor_empenhado"]:
    algum_nulo = algum_nulo | F.col(coluna).isNull()
registrar("Fato", "colunas obrigatórias nulas", fato.where(algum_nulo).count())

# SCD tipo 2 no fato: a sk tem que ser da mesma chave natural da Silver e da versão válida na data de emissão.
# Sem código na Silver, o empenho aponta para o membro -1.
momento = F.col("data_emissao").cast("timestamp")
for sk, dim, chave_dim, chave_silver in [
    ("sk_municipio", "dim_municipio", "ibge", "ibge"),
    ("sk_funcao", "dim_funcao", "codigo", "codigo_funcao"),
    ("sk_elemento", "dim_elemento_despesa", "codigo", "codigo_elemento"),
]:
    versoes = spark.table(f"{SCHEMA_GOLD}.{dim}").select(
        sk, F.col(chave_dim).alias("chave_dim"), "data_inicio", "data_fim")
    versao_certa = (
        F.col("chave_dim").eqNullSafe(F.col(chave_silver))
        & (momento >= F.col("data_inicio"))
        & (momento < F.col("data_fim"))
    )
    sem_codigo_errado = (F.col(sk) != -1) | F.col("data_inicio").isNull()
    erradas = (
        comparado.join(versoes, sk, "left")
        .where(F.when(F.col(chave_silver).isNull(), sem_codigo_errado).otherwise(~versao_certa))
        .count()
    )
    registrar("Fato", f"{sk} na versão errada da {dim}", erradas)

# Avisos: dependem do que os portais publicam, e não de erro do pipeline.
registrar("Fato", "empenhado negativo (anulações maiores que o valor)",
          fato.where(F.col("valor_empenhado") < 0).count(), aviso=True)
atende = spark.table(f"{SCHEMA_GOLD}.dim_municipio").where(F.col("ibge").isin(ATENDE_NET)).select("sk_municipio")
registrar("Fato", "empenhos do Atende.net com função ou anulação",
          fato.join(atende, "sk_municipio", "left_semi")
          .where((F.col("sk_funcao") != -1) | (F.col("valor_anulado") != 0))
          .count(),
          aviso=True)

# COMMAND ----------

# MAGIC %md
# MAGIC ## fato_populacao

# COMMAND ----------

populacao = spark.table(f"{SCHEMA_GOLD}.fato_populacao")
esperado = (
    spark.table(f"{SCHEMA_GOLD}.dim_municipio").where("registro_atual").select("sk_municipio")
    .crossJoin(spark.range(2023, 2027).select(F.col("id").cast("smallint").alias("ano")))
)
registrar("População", "município e ano sem população",
          esperado.join(populacao.where(F.col("populacao") > 0), ["sk_municipio", "ano"], "left_anti").count())
registrar("População", "município e ano repetido", repetidas(populacao, ["sk_municipio", "ano"]))

# COMMAND ----------

# MAGIC %md
# MAGIC ## Tabelas do dashboard
# MAGIC
# MAGIC As tabelas `agg_` são recalculadas aqui direto do fato e comparadas por município e ano.

# COMMAND ----------

agg = spark.table(f"{SCHEMA_GOLD}.agg_empenhado_municipio_ano")
agg_area = spark.table(f"{SCHEMA_GOLD}.agg_empenhado_area")
municipio = spark.table(f"{SCHEMA_GOLD}.dim_municipio").select("sk_municipio", "ibge")

registrar("Agregados", "município e ano repetido na agg_empenhado_municipio_ano", repetidas(agg, ["ibge", "ano"]))
registrar("Agregados", "município, ano e área repetidos na agg_empenhado_area",
          repetidas(agg_area, ["ibge", "ano", "area"]))

do_fato = (
    fato.join(municipio, "sk_municipio")
    .groupBy("ibge", "ano")
    .agg(
        F.count(F.lit(1)).alias("empenhos"),
        F.sum("valor_empenhado").cast("decimal(18,2)").alias("empenhado_total"),
    )
)
da_agg = agg.select("ibge", "ano", "empenhos", "empenhado_total")
registrar("Agregados", "município e ano com empenhos ou empenhado diferente do fato",
          da_agg.exceptAll(do_fato).count() + do_fato.exceptAll(da_agg).count())

soma_grupos = (F.col("empenhado_pessoal") + F.col("empenhado_custeio")
               + F.col("empenhado_investimento") + F.col("empenhado_outros_grupos"))
registrar("Agregados", "pessoal + custeio + investimento + outros diferente do total",
          agg.where(soma_grupos != F.col("empenhado_total")).count())

# Somando as áreas, cada município e ano tem que dar o mesmo total e a mesma população da outra tabela.
por_area = agg_area.groupBy("ibge", "ano").agg(
    F.sum("empenhado").cast("decimal(18,2)").alias("empenhado_total"),
    F.max("populacao").alias("populacao"),
)
totais = agg.select("ibge", "ano", "empenhado_total", "populacao")
registrar("Agregados", "município e ano em que as áreas não batem com o total",
          por_area.exceptAll(totais).count() + totais.exceptAll(por_area).count())

registrar("Agregados", "linhas sem população",
          agg.where(F.col("populacao").isNull()).count() + agg_area.where(F.col("populacao").isNull()).count())

# COMMAND ----------

# MAGIC %md
# MAGIC ## Indicadores
# MAGIC
# MAGIC Os 4 indicadores (`docs/gold.md`) são calculados de dois jeitos: pela `agg_empenhado_municipio_ano`, como
# MAGIC no dashboard, e direto do fato. As somas de cada ano têm que ser iguais. Como na agg, a população só conta
# MAGIC para o município e ano que tem empenho.

# COMMAND ----------

pela_agg = agg.groupBy("ano").agg(
    F.sum("empenhado_total").alias("total"),
    F.sum("empenhado_pessoal").alias("pessoal"),
    F.sum("empenhado_saude").alias("saude"),
    F.sum("empenhado_com_funcao").alias("com_funcao"),
    F.sum("populacao").alias("populacao"),
)


def soma_se(condicao):
    return F.sum(F.when(condicao, F.col("valor_empenhado")).otherwise(F.lit(0)))


valores = (
    fato
    .join(spark.table(f"{SCHEMA_GOLD}.dim_funcao").select("sk_funcao", "area"), "sk_funcao")
    .join(spark.table(f"{SCHEMA_GOLD}.dim_elemento_despesa").select("sk_elemento", "grupo_despesa"), "sk_elemento")
    .groupBy("ano")
    .agg(
        F.sum("valor_empenhado").alias("total"),
        soma_se(F.col("grupo_despesa") == "Pessoal").alias("pessoal"),
        soma_se(F.col("area") == "Saúde").alias("saude"),
        soma_se(F.col("area") != "Não informada").alias("com_funcao"),
    )
)
populacao_com_empenho = (
    populacao.join(municipio, "sk_municipio")
    .join(do_fato.select("ibge", "ano"), ["ibge", "ano"], "left_semi")
    .groupBy("ano")
    .agg(F.sum("populacao").alias("populacao"))
)
pelo_fato = valores.join(populacao_com_empenho, "ano", "left")

diferente = F.lit(False)
for coluna in ["total", "pessoal", "saude", "com_funcao", "populacao"]:
    diferente = diferente | ~F.col(f"a.{coluna}").eqNullSafe(F.col(f"f.{coluna}"))
registrar("Indicadores", "anos em que a agg e o fato dão somas diferentes",
          pela_agg.alias("a").join(pelo_fato.alias("f"), "ano", "full").where(diferente).count())

indicadores = pela_agg.select(
    "ano",
    F.col("total").alias("total_empenhado"),
    F.round(F.col("total") / F.col("populacao"), 2).alias("empenhado_por_habitante"),
    F.round(F.col("pessoal") / F.col("total") * 100, 1).alias("pct_pessoal"),
    F.round(F.col("saude") / F.col("com_funcao") * 100, 1).alias("pct_saude"),
).orderBy("ano")
registrar("Indicadores", "anos com indicador fora do intervalo",
          indicadores.where((F.col("empenhado_por_habitante") <= 0)
                            | ~F.col("pct_pessoal").between(0, 100)
                            | ~F.col("pct_saude").between(0, 100))
          .count())

display(indicadores)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Resultado

# COMMAND ----------

display(spark.createDataFrame(resultados, "grupo string, teste string, situacao string, problemas bigint"))

falhas = [r for r in resultados if r[2] == "FALHOU"]
avisos = [r for r in resultados if r[2] == "AVISO"]
print(f"{len(resultados)} testes: {len(resultados) - len(falhas) - len(avisos)} OK, "
      f"{len(falhas)} falharam, {len(avisos)} aviso(s)")

if falhas:
    raise ValueError("Testes da Gold: " + "; ".join(f"{teste} ({problemas})" for _, teste, _, problemas in falhas))
