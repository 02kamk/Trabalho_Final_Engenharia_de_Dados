"""Ingestão incremental: Neon → Landing (CSV no Azure Data Lake Storage).

Adaptação do databricks/03_landing_incremental.py (issue #12). Lê as 15 tabelas do esquema `origem` do Neon
por JDBC e grava em CSV bruto em <lake>/landing/<tabela>/run_id=<execução>/.

Carga incremental: toda tabela da origem tem `atualizado_em`. A tabela de controle <lake>/controle/controle_landing
guarda o maior valor já carregado de cada tabela (o watermark). Cada execução busca no Neon só as linhas com
`atualizado_em` maior que esse valor; o filtro roda no próprio Postgres, então só o que mudou é transferido.

- Primeira execução: sem watermark, carrega tudo.
- Próximas execuções: só o que foi inserido ou alterado desde a última.
- Tabela sem novidade: nada é gravado.
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/pipeline")

from comum import (  # noqa: E402
    FORMATO_TIMESTAMP, TABELAS_ORIGEM, apagar, caminho, criar_spark, garantir_tabela, gravar, ler, ler_neon, mostrar,
)
from pyspark.sql import functions as F  # noqa: E402

RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

ESQUEMA_CONTROLE = (
    "tabela string, run_id string, watermark_anterior timestamp, watermark_novo timestamp, "
    "linhas bigint, caminho string, executado_em timestamp"
)

spark = criar_spark("amrec_03_landing")
print(f"run_id: {RUN_ID}")

# Tabela de controle: uma linha por execução e por tabela.
garantir_tabela(spark, "controle", "controle_landing", ESQUEMA_CONTROLE)


def ultimo_watermark(tabela):
    """Maior atualizado_em já carregado (timestamp e texto em UTC para o filtro no Postgres), ou (None, None)."""
    linha = (
        ler(spark, "controle", "controle_landing")
        .where(F.col("tabela") == tabela)
        .agg(F.max("watermark_novo").alias("wm"))
        .select("wm", F.date_format("wm", "yyyy-MM-dd HH:mm:ss.SSSSSS").alias("wm_texto"))
        .first()
    )
    return linha["wm"], linha["wm_texto"]


def ingerir(tabela):
    watermark, watermark_texto = ultimo_watermark(tabela)

    consulta = f"SELECT * FROM origem.{tabela}"
    if watermark is not None:
        # A sessão do Spark está em UTC; o "+00" garante que o Postgres compare no mesmo fuso.
        consulta += f" WHERE atualizado_em > '{watermark_texto}+00'::timestamptz"
    origem = ler_neon(spark, consulta)

    destino = caminho("landing", f"{tabela}/run_id={RUN_ID}")

    # Landing: CSV bruto, sem regra de negócio.
    (
        origem.write
        .mode("overwrite")
        .option("header", "true")
        .option("timestampFormat", FORMATO_TIMESTAMP)
        .csv(destino)
    )

    # Conferência: lê de volta o que foi gravado e calcula o novo watermark a partir dele.
    gravado = (
        spark.read
        .option("header", "true")
        .option("multiLine", "true")
        .csv(destino)
        .withColumn("atualizado_em", F.to_timestamp("atualizado_em", FORMATO_TIMESTAMP))
    )
    resumo = gravado.agg(F.count(F.lit(1)).alias("linhas"), F.max("atualizado_em").alias("wm")).first()
    linhas = resumo["linhas"]

    if linhas == 0:
        # Sem novidade: remove a pasta vazia e mantém o watermark anterior.
        apagar(spark, destino)
        novo_watermark, destino = watermark, None
    else:
        novo_watermark = resumo["wm"]
        if novo_watermark is None:
            raise ValueError(f"{tabela}: atualizado_em ficou nulo após a leitura do CSV")

    gravar(
        spark.createDataFrame(
            [(tabela, RUN_ID, watermark, novo_watermark, linhas, destino, datetime.now(timezone.utc))],
            ESQUEMA_CONTROLE,
        ),
        "controle", "controle_landing", "append",
    )

    print(f"{tabela:<30} {linhas:>10,} linhas  (watermark: {watermark} → {novo_watermark})")
    return linhas


total = sum(ingerir(tabela) for tabela in TABELAS_ORIGEM)
print(f"\nTotal gravado na Landing nesta execução: {total:,} linhas")

mostrar(ler(spark, "controle", "controle_landing").where(F.col("run_id") == RUN_ID).orderBy("tabela"))
spark.stop()
