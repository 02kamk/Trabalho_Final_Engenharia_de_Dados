"""Teste de ponta a ponta da infraestrutura: Neon → Spark → Delta no Azure Data Lake Storage.

1. Lê origem.municipio do Neon por JDBC (esperado: 12 linhas).
2. Grava como tabela Delta em <lake>/_teste/municipio.
3. Lê de volta, faz um MERGE (o mesmo recurso usado na Silver e na Gold) e confere o histórico do Delta.

Não altera nada no Neon e só grava na pasta _teste/ do lake. Pode ser rodado quantas vezes quiser.
"""

import sys

sys.path.insert(0, "/opt/airflow/pipeline")

from comum import caminho, criar_spark, ler_neon, raiz_lake  # noqa: E402
from delta.tables import DeltaTable  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

spark = criar_spark("amrec_teste_conexao", memoria_driver="1g")
print(f"Spark {spark.version} | lake: {raiz_lake()}")

# 1. Neon
municipios = ler_neon(spark, "SELECT ibge, nome, fonte, atualizado_em FROM origem.municipio")
linhas_neon = municipios.count()
print(f"[1/3] Neon: origem.municipio tem {linhas_neon} linhas")
if linhas_neon != 12:
    raise SystemExit(f"Esperado 12 municípios no Neon, veio {linhas_neon}")

# 2. Gravação Delta no Azure
destino = caminho("_teste", "municipio")
municipios.write.format("delta").mode("overwrite").save(destino)
linhas_lake = spark.read.format("delta").load(destino).count()
print(f"[2/3] Azure: tabela Delta gravada em {destino} com {linhas_lake} linhas")
if linhas_lake != linhas_neon:
    raise SystemExit("A leitura do lake não bateu com o Neon")

# 3. MERGE: atualiza um município e confere que o total não muda e que o Delta registrou a versão.
alteracao = municipios.where("ibge = '4204608'").withColumn("nome", F.concat(F.col("nome"), F.lit(" (teste)")))
(
    DeltaTable.forPath(spark, destino).alias("alvo")
    .merge(alteracao.alias("novo"), "alvo.ibge = novo.ibge")
    .whenMatchedUpdateAll()
    .whenNotMatchedInsertAll()
    .execute()
)
depois = spark.read.format("delta").load(destino)
alterados = depois.where(F.col("nome").endswith(" (teste)")).count()
versoes = DeltaTable.forPath(spark, destino).history().select("version", "operation").orderBy("version")
print(f"[3/3] MERGE: {depois.count()} linhas, {alterados} alterada(s)")
versoes.show(truncate=False)
if depois.count() != 12 or alterados != 1:
    raise SystemExit("O MERGE não teve o resultado esperado")

print("OK: Neon, Spark, Delta e Azure Data Lake Storage funcionando juntos.")
spark.stop()
