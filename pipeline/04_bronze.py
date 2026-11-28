"""Transformação: Landing (CSV) → Bronze (Delta no Azure Data Lake Storage).

Adaptação do databricks/04_bronze.py (issue #13). Lê os CSVs de <lake>/landing/<tabela>/run_id=<execução>/ e
grava uma tabela Delta por tabela da origem em <lake>/bronze/<tabela>.

Regras da Bronze:
- O conteúdo não é alterado: todas as colunas ficam como texto, do jeito que vieram do CSV. A tipagem e a
  limpeza ficam para a Silver.
- Cada linha ganha colunas de controle: `_run_id`, `_arquivo_origem` e `_data_ingestao`.
- Os dados só são acrescentados (append), nunca sobrescritos: a Bronze guarda o histórico de tudo o que chegou.

Carga incremental: <lake>/controle/controle_bronze registra quais execuções da Landing (`run_id`) já foram
processadas. Cada execução deste script processa só as execuções que ainda não estão nesse controle. O controle
só é gravado depois da carga conferida, então uma falha no meio pode ser corrigida rodando o script de novo.
"""

import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/pipeline")

from comum import (  # noqa: E402
    TABELAS_ORIGEM, criar_spark, existe, garantir_tabela, gravar, ler, mostrar, tabela_delta,
)
from pyspark.sql import functions as F  # noqa: E402

EXECUCAO_BRONZE = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

ESQUEMA_CONTROLE = (
    "tabela string, run_id_landing string, execucao_bronze string, linhas bigint, processado_em timestamp"
)

spark = criar_spark("amrec_04_bronze")
print(f"Execução da Bronze: {EXECUCAO_BRONZE}")

garantir_tabela(spark, "controle", "controle_bronze", ESQUEMA_CONTROLE)


def execucoes_pendentes(tabela):
    """Execuções da Landing com arquivo gravado e que ainda não foram para a Bronze."""
    landing = (
        ler(spark, "controle", "controle_landing")
        .where((F.col("tabela") == tabela) & F.col("caminho").isNotNull() & (F.col("linhas") > 0))
        .select("run_id", "caminho", "linhas")
    )
    processadas = (
        ler(spark, "controle", "controle_bronze")
        .where(F.col("tabela") == tabela)
        .select(F.col("run_id_landing").alias("run_id"))
    )
    pendentes = landing.join(processadas, "run_id", "left_anti").orderBy("run_id")
    return [(linha["run_id"], linha["caminho"], linha["linhas"]) for linha in pendentes.collect()]


def processar(tabela):
    pendentes = execucoes_pendentes(tabela)
    if not pendentes:
        print(f"{tabela:<30} nada novo na Landing")
        return 0

    total = 0
    for run_id, origem, esperado in pendentes:
        # Tudo como texto: a Bronze guarda o dado bruto, sem interpretar tipos.
        # multiLine permite textos com quebra de linha (como o histórico do empenho).
        dados = (
            spark.read
            .option("header", "true")
            .option("inferSchema", "false")
            .option("multiLine", "true")
            .csv(origem)
            .withColumn("_run_id", F.lit(run_id))
            .withColumn("_arquivo_origem", F.col("_metadata.file_path"))
            .withColumn("_data_ingestao", F.current_timestamp())
        )

        # Se uma tentativa anterior gravou esta execução e caiu antes do controle, remove as linhas dela antes
        # de gravar de novo. Assim a Bronze não duplica a execução ao reprocessar.
        if existe(spark, "bronze", tabela):
            tabela_delta(spark, "bronze", tabela).delete(F.col("_run_id") == run_id)

        gravar(dados, "bronze", tabela, "append")

        # Conferência: as linhas gravadas nesta execução devem bater com o controle da Landing.
        linhas = ler(spark, "bronze", tabela).where(F.col("_run_id") == run_id).count()
        if linhas != esperado:
            raise ValueError(f"{tabela} run_id={run_id}: Bronze tem {linhas} linhas, a Landing registrou {esperado}")

        gravar(
            spark.createDataFrame(
                [(tabela, run_id, EXECUCAO_BRONZE, linhas, datetime.now(timezone.utc))], ESQUEMA_CONTROLE
            ),
            "controle", "controle_bronze", "append",
        )

        print(f"{tabela:<30} run_id={run_id}  {linhas:>10,} linhas")
        total += linhas

    return total


total = sum(processar(tabela) for tabela in TABELAS_ORIGEM)
print(f"\nTotal gravado na Bronze nesta execução: {total:,} linhas")

mostrar(ler(spark, "controle", "controle_bronze").where(F.col("execucao_bronze") == EXECUCAO_BRONZE).orderBy("tabela", "run_id_landing"))
spark.stop()
