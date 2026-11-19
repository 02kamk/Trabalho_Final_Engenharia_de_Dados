# Databricks notebook source
# MAGIC %md
# MAGIC # Piloto: Neon → Landing cloud
# MAGIC
# MAGIC Ingestão da tabela `origem.municipio` do catálogo federado Neon
# MAGIC para a camada Landing em CSV bruto.

from datetime import datetime, timezone

CATALOGO_ORIGEM = "neon_origem_catalog"
TABELA_ORIGEM = f"{CATALOGO_ORIGEM}.origem.municipio"

CATALOGO_DESTINO = "workspace"
SCHEMA_LANDING = "amrec"
VOLUME_LANDING = "landing"

# Preparação idempotente da estrutura cloud.
spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO_DESTINO}.{SCHEMA_LANDING}")
spark.sql(
    f"CREATE VOLUME IF NOT EXISTS "
    f"{CATALOGO_DESTINO}.{SCHEMA_LANDING}.{VOLUME_LANDING}"
)

for camada in ("amrec_bronze", "amrec_silver", "amrec_gold"):
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO_DESTINO}.{camada}")

# Leitura da origem federada no Neon.
origem_municipio = spark.table(TABELA_ORIGEM)
linhas_origem = origem_municipio.count()

# Cada execução recebe um diretório próprio para preservar o histórico bruto.
run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
destino_landing = (
    f"/Volumes/{CATALOGO_DESTINO}/{SCHEMA_LANDING}/{VOLUME_LANDING}"
    f"/municipio/run_id={run_id}"
)

# Landing: CSV bruto, sem transformação de negócio.
(
    origem_municipio
    .coalesce(1)  # adequado apenas ao piloto de 12 linhas
    .write
    .mode("overwrite")
    .option("header", "true")
    .csv(destino_landing)
)

# Validação de leitura após escrita.
linhas_landing = (
    spark.read
    .option("header", "true")
    .csv(destino_landing)
    .count()
)

if linhas_origem != linhas_landing:
    raise ValueError(
        f"Validação falhou: origem={linhas_origem}, landing={linhas_landing}"
    )

print(f"Origem: {TABELA_ORIGEM}")
print(f"Destino: {destino_landing}")
print(f"Linhas gravadas na Landing: {linhas_landing}")