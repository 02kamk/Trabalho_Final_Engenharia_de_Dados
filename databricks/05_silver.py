# Databricks notebook source
# MAGIC %md
# MAGIC # Transformação: Bronze → Silver (Delta)
# MAGIC
# MAGIC Issue #14. Lê as tabelas da Bronze (tudo como texto) e grava no schema
# MAGIC `workspace.amrec_silver` com os tipos corretos e uma linha por chave.
# MAGIC
# MAGIC **O que a Silver faz:**
# MAGIC 1. **Tipagem:** converte cada coluna para o tipo da origem (número, data, decimal, booleano),
# MAGIC    conforme o `sql/origem.sql`.
# MAGIC 2. **Limpeza:** tira espaços das pontas dos textos e transforma texto vazio em nulo.
# MAGIC 3. **Qualidade:** confere se algum valor não pôde ser convertido e se alguma chave primária
# MAGIC    ficou nula. Se acontecer, a execução para com erro.
# MAGIC 4. **Deduplicação:** se a mesma chave chegou mais de uma vez (por exemplo, um registro alterado
# MAGIC    na origem), fica só a versão mais recente, pelo `atualizado_em`.
# MAGIC 5. **MERGE:** atualiza as linhas que já existem na Silver e insere as novas.
# MAGIC
# MAGIC **Carga incremental:** a tabela `workspace.amrec.controle_silver` registra quais execuções
# MAGIC da Landing (`run_id`) já foram aplicadas na Silver. Cada execução processa só as pendentes.

# COMMAND ----------

from datetime import datetime, timezone

from delta.tables import DeltaTable
from pyspark.sql import Window
from pyspark.sql import functions as F

CATALOGO = "workspace"
SCHEMA_BRONZE = "amrec_bronze"
SCHEMA_SILVER = "amrec_silver"
CONTROLE_BRONZE = f"{CATALOGO}.amrec.controle_bronze"
CONTROLE_SILVER = f"{CATALOGO}.amrec.controle_silver"

# Formato em que a Landing gravou o atualizado_em (ver 03_landing_incremental).
FORMATO_TIMESTAMP = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX"

DECIMAL_VALOR = "decimal(15,2)"
DECIMAL_QTDE = "decimal(18,4)"

# Chave primária e colunas de cada tabela, na ordem do sql/origem.sql.
# Colunas não listadas no dicionário de tipos ficam como texto (string).
TABELAS = {
    # Domínios e cadastros
    "municipio": {
        "pk": ["ibge"],
        "colunas": ["ibge", "nome", "fonte", "data_coleta"],
        "tipos": {"data_coleta": "date"},
    },
    "funcao": {
        "pk": ["codigo"],
        "colunas": ["codigo", "nome"],
        "tipos": {"codigo": "smallint"},
    },
    "elemento_despesa": {
        "pk": ["codigo"],
        "colunas": ["codigo", "nome"],
        "tipos": {},
    },
    "credor": {
        "pk": ["id_credor"],
        "colunas": ["id_credor", "documento", "nome"],
        "tipos": {"id_credor": "int"},
    },
    "material": {
        "pk": ["id_material"],
        "colunas": ["id_material", "descricao", "unidade_medida"],
        "tipos": {"id_material": "int"},
    },
    "documento_fiscal": {
        "pk": ["id_documento"],
        "colunas": ["id_documento", "id_emitente", "tipo", "numero", "data_emissao", "chave_acesso"],
        "tipos": {"id_documento": "bigint", "id_emitente": "int", "data_emissao": "date"},
    },
    # Execução da despesa
    "empenho": {
        "pk": ["id_empenho"],
        "colunas": [
            "id_empenho", "ibge", "id_origem", "entidade", "numero", "ano", "data_emissao", "tipo",
            "id_credor", "codigo_elemento", "elemento_inferido", "codigo_funcao", "historico", "valor",
        ],
        "tipos": {
            "id_empenho": "bigint", "numero": "int", "ano": "smallint", "data_emissao": "date",
            "id_credor": "int", "elemento_inferido": "boolean", "codigo_funcao": "smallint",
            "valor": DECIMAL_VALOR,
        },
    },
    "item_empenho": {
        "pk": ["id_empenho", "sequencia"],
        "colunas": ["id_empenho", "sequencia", "id_material", "quantidade", "valor_unitario", "valor_total"],
        "tipos": {
            "id_empenho": "bigint", "sequencia": "smallint", "id_material": "int",
            "quantidade": DECIMAL_QTDE, "valor_unitario": DECIMAL_QTDE, "valor_total": DECIMAL_VALOR,
        },
    },
    "empenho_documento_fiscal": {
        "pk": ["id_empenho", "id_documento"],
        "colunas": ["id_empenho", "id_documento", "valor"],
        "tipos": {"id_empenho": "bigint", "id_documento": "bigint", "valor": DECIMAL_VALOR},
    },
    "anulacao_empenho": {
        "pk": ["id_empenho", "sequencia"],
        "colunas": ["id_empenho", "sequencia", "data", "tipo", "motivo", "valor"],
        "tipos": {"id_empenho": "bigint", "sequencia": "smallint", "data": "date", "valor": DECIMAL_VALOR},
    },
    "liquidacao": {
        "pk": ["id_liquidacao"],
        "colunas": ["id_liquidacao", "id_empenho", "numero", "data", "valor", "valor_anulado"],
        "tipos": {
            "id_liquidacao": "bigint", "id_empenho": "bigint", "data": "date",
            "valor": DECIMAL_VALOR, "valor_anulado": DECIMAL_VALOR,
        },
    },
    "retencao": {
        "pk": ["id_retencao"],
        "colunas": ["id_retencao", "id_liquidacao", "id_empenho", "data", "valor"],
        "tipos": {
            "id_retencao": "bigint", "id_liquidacao": "bigint", "id_empenho": "bigint",
            "data": "date", "valor": DECIMAL_VALOR,
        },
    },
    "pagamento": {
        "pk": ["id_pagamento"],
        "colunas": ["id_pagamento", "id_empenho", "numero_ordem", "data", "valor", "valor_anulado", "historico"],
        "tipos": {
            "id_pagamento": "bigint", "id_empenho": "bigint", "data": "date",
            "valor": DECIMAL_VALOR, "valor_anulado": DECIMAL_VALOR,
        },
    },
    "diaria": {
        "pk": ["id_diaria"],
        "colunas": [
            "id_diaria", "ibge", "id_credor", "entidade", "cargo", "data_inicio", "data_fim",
            "destino", "finalidade", "quantidade", "valor",
        ],
        "tipos": {
            "id_diaria": "bigint", "id_credor": "int", "data_inicio": "date", "data_fim": "date",
            "quantidade": "decimal(8,2)", "valor": DECIMAL_VALOR,
        },
    },
    "pagamento_extraorcamentario": {
        "pk": ["id_pagamento_extra"],
        "colunas": ["id_pagamento_extra", "ibge", "conta", "id_credor", "data", "valor", "historico"],
        "tipos": {"id_pagamento_extra": "bigint", "id_credor": "int", "data": "date", "valor": DECIMAL_VALOR},
    },
}

EXECUCAO_SILVER = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
print(f"Execução da Silver: {EXECUCAO_SILVER}")

spark.sql(f"CREATE SCHEMA IF NOT EXISTS {CATALOGO}.{SCHEMA_SILVER}")

spark.sql(f"""
    CREATE TABLE IF NOT EXISTS {CONTROLE_SILVER} (
        tabela            STRING    NOT NULL,
        run_id_landing    STRING    NOT NULL,
        execucao_silver   STRING    NOT NULL,
        linhas_lidas      BIGINT    NOT NULL,
        linhas_aplicadas  BIGINT    NOT NULL,
        processado_em     TIMESTAMP NOT NULL
    ) USING DELTA
""")

# COMMAND ----------

def execucoes_pendentes(tabela):
    """Execuções da Landing que já estão na Bronze e ainda não foram aplicadas na Silver."""
    na_bronze = (
        spark.table(CONTROLE_BRONZE)
        .where(F.col("tabela") == tabela)
        .select(F.col("run_id_landing").alias("run_id"))
        .distinct()
    )
    na_silver = (
        spark.table(CONTROLE_SILVER)
        .where(F.col("tabela") == tabela)
        .select(F.col("run_id_landing").alias("run_id"))
    )
    pendentes = na_bronze.join(na_silver, "run_id", "left_anti").orderBy("run_id")
    return [linha["run_id"] for linha in pendentes.collect()]


def tipar_e_limpar(bronze, config):
    """Converte cada coluna para o tipo da origem e limpa os textos."""
    colunas = []
    for coluna in config["colunas"]:
        texto = F.nullif(F.trim(F.col(coluna)), F.lit(""))
        tipo = config["tipos"].get(coluna, "string")
        if tipo == "string":
            colunas.append(texto.alias(coluna))
        else:
            # try_cast devolve nulo em vez de quebrar; a conferência abaixo pega esses casos.
            colunas.append(F.expr(f"try_cast(nullif(trim(`{coluna}`), '') AS {tipo})").alias(coluna))

    colunas.append(
        F.expr(f"try_to_timestamp(atualizado_em, '{FORMATO_TIMESTAMP}')").alias("atualizado_em")
    )
    colunas += [F.col("_run_id"), F.col("_data_ingestao")]
    return bronze.select(*colunas)

# COMMAND ----------

def preparar(tabela, config, run_ids):
    """Lê da Bronze as execuções pendentes, tipa, confere a qualidade e deduplica."""
    bronze = spark.table(f"{CATALOGO}.{SCHEMA_BRONZE}.{tabela}").where(F.col("_run_id").isin(run_ids))
    linhas_lidas = bronze.count()

    tipado = tipar_e_limpar(bronze, config)

    colunas_tipadas = list(config["tipos"]) + ["atualizado_em"]

    # Conferência de qualidade feita com uma única leitura da Bronze.
    conferencia = bronze.select(
        *[
            (
                F.nullif(F.trim(F.col(c)), F.lit("")).isNotNull()
                & (
                    F.expr(f"try_to_timestamp(atualizado_em, '{FORMATO_TIMESTAMP}')")
                    if c == "atualizado_em"
                    else F.expr(f"try_cast(nullif(trim(`{c}`), '') AS {config['tipos'][c]})")
                ).isNull()
            ).cast("int").alias(f"falha_{c}")
            for c in colunas_tipadas
        ],
        *[
            F.nullif(F.trim(F.col(pk)), F.lit("")).isNull().cast("int").alias(f"pk_nula_{pk}")
            for pk in config["pk"]
        ],
    )
    totais = conferencia.agg(*[F.sum(c).alias(c) for c in conferencia.columns]).first().asDict()
    problemas = [f"{nome}: {qtd} linha(s)" for nome, qtd in totais.items() if qtd]
    if problemas:
        raise ValueError(f"{tabela}: problemas de qualidade -> " + "; ".join(problemas))

    # Uma linha por chave: a versão mais recente pelo atualizado_em (e, no empate, a última ingestão).
    janela = Window.partitionBy(*config["pk"]).orderBy(
        F.col("atualizado_em").desc(), F.col("_data_ingestao").desc()
    )
    deduplicado = (
        tipado.withColumn("_ordem", F.row_number().over(janela))
        .where(F.col("_ordem") == 1)
        .drop("_ordem", "_data_ingestao")
        .withColumn("_processado_silver_em", F.current_timestamp())
    )
    return deduplicado, linhas_lidas


def aplicar(tabela, config, dados):
    """Insere na Silver ou, se a tabela já existe, faz MERGE pela chave primária."""
    destino = f"{CATALOGO}.{SCHEMA_SILVER}.{tabela}"

    if not spark.catalog.tableExists(destino):
        dados.write.format("delta").saveAsTable(destino)
        return

    condicao = " AND ".join(f"alvo.{pk} = novo.{pk}" for pk in config["pk"])
    (
        DeltaTable.forName(spark, destino).alias("alvo")
        .merge(dados.alias("novo"), condicao)
        # Só atualiza se a versão que chegou for mais nova que a que já está na Silver.
        .whenMatchedUpdateAll(condition="novo.atualizado_em >= alvo.atualizado_em")
        .whenNotMatchedInsertAll()
        .execute()
    )


def processar(tabela):
    config = TABELAS[tabela]
    run_ids = execucoes_pendentes(tabela)
    if not run_ids:
        print(f"{tabela:<30} nada novo na Bronze")
        return 0

    dados, linhas_lidas = preparar(tabela, config, run_ids)
    linhas_aplicadas = dados.count()
    aplicar(tabela, config, dados)

    registros = [
        (tabela, run_id, EXECUCAO_SILVER, linhas_lidas, linhas_aplicadas, datetime.now(timezone.utc))
        for run_id in run_ids
    ]
    spark.createDataFrame(
        registros,
        "tabela string, run_id_landing string, execucao_silver string, "
        "linhas_lidas bigint, linhas_aplicadas bigint, processado_em timestamp",
    ).write.mode("append").saveAsTable(CONTROLE_SILVER)

    print(f"{tabela:<30} lidas {linhas_lidas:>10,}  aplicadas {linhas_aplicadas:>10,}  ({len(run_ids)} execução(ões))")
    return linhas_aplicadas

# COMMAND ----------

total = 0
for tabela in TABELAS:
    total += processar(tabela)

print(f"\nTotal aplicado na Silver nesta execução: {total:,} linhas")

# COMMAND ----------

# Conferência final: quantidade de linhas e de chaves distintas em cada tabela da Silver.
# Se a Silver estiver correta, as duas colunas são iguais (uma linha por chave).
resumo = []
for tabela, config in TABELAS.items():
    destino = f"{CATALOGO}.{SCHEMA_SILVER}.{tabela}"
    if not spark.catalog.tableExists(destino):
        continue
    silver = spark.table(destino)
    resumo.append((
        tabela,
        silver.count(),
        silver.select(*config["pk"]).distinct().count(),
    ))

display(spark.createDataFrame(resumo, "tabela string, linhas bigint, chaves_distintas bigint"))
