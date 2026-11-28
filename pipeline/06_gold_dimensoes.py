"""Gold: dimensões (SCD tipo 2) no Azure Data Lake Storage.

Adaptação do databricks/06_gold_dimensoes.py (issues #65, #16 e #17). Lê <lake>/silver/<tabela> e grava as
dimensões do modelo dimensional em <lake>/gold/<dimensao>. O modelo está descrito em docs/gold.md.

| Dimensão               | Chave natural | Atributos                 | Origem                                              |
| ---------------------- | ------------- | ------------------------- | --------------------------------------------------- |
| dim_municipio          | ibge          | nome, fonte, data_coleta  | silver/municipio                                    |
| dim_funcao             | codigo        | nome, area                | silver/funcao                                       |
| dim_elemento_despesa   | codigo        | nome, grupo_despesa       | silver/elemento_despesa + referencia/elemento_grupo |
| dim_data               | data          | ano, mês, trimestre       | gerada aqui, sem SCD                                |

SCD tipo 2: cada dimensão tem data_inicio, data_fim e registro_atual. Quando um atributo muda na origem, a versão
atual é fechada (data_fim = momento da alteração, registro_atual = falso) e uma nova versão é inserida. A primeira
versão de cada chave vale desde 1900-01-01, para que os fatos anteriores à primeira carga encontrem uma versão.

Membro desconhecido: dim_funcao e dim_elemento_despesa têm a linha sk = -1 ("Não informada"), usada pelos
empenhos sem função (todo o Atende.net) ou sem elemento.

O que mudou em relação ao Databricks:
- As tabelas são pastas no lake (comum.ler / comum.gravar / comum.tabela_delta), não nomes no catálogo.
- A sk não é mais uma coluna de identidade do Delta: é calculada aqui, como a maior sk existente + 1, 2, 3...
- O elemento_grupo.csv é copiado de databricks/referencia/ para <lake>/referencia/ e lido de lá.

As dimensões são pequenas (12, 28 e 50 linhas), então cada execução compara a Silver inteira com a versão atual
de cada chave. Reexecutar sem mudanças na origem não altera nada.
"""

import sys

sys.path.insert(0, "/opt/airflow/pipeline")

from comum import (  # noqa: E402
    criar_spark, garantir_tabela, gravar, ler, mostrar, publicar_referencia, tabela_delta,
)
from pyspark.sql import Window  # noqa: E402
from pyspark.sql import functions as F  # noqa: E402

INICIO_VALIDADE = "1900-01-01 00:00:00"
FIM_VALIDADE = "9999-12-31 00:00:00"

# Áreas do dashboard, pelo código nacional da função (Portaria MOG 42/1999).
AREAS = {4: "Administração", 10: "Saúde", 12: "Educação", 15: "Urbanismo"}

# Grupo de natureza de despesa (2º dígito da natureza) → rótulo usado no dashboard.
# Juros (2), inversões (5) e amortização (6) ficam em "Outros".
GRUPOS = {"1": "Pessoal", "3": "Custeio", "4": "Investimento"}

COLUNAS_SCD = "data_inicio timestamp, data_fim timestamp, registro_atual boolean, hash_atributos string"

ESQUEMAS = {
    "dim_municipio": f"sk_municipio bigint, ibge string, nome string, fonte string, data_coleta date, {COLUNAS_SCD}",
    "dim_funcao": f"sk_funcao bigint, codigo smallint, nome string, area string, {COLUNAS_SCD}",
    "dim_elemento_despesa": f"sk_elemento bigint, codigo string, nome string, grupo_despesa string, {COLUNAS_SCD}",
}

spark = criar_spark("amrec_06_gold_dimensoes")

for dimensao, esquema in ESQUEMAS.items():
    garantir_tabela(spark, "gold", dimensao, esquema)


def garantir_membro_desconhecido(dimensao, esquema_atributos, valores):
    """Insere a linha sk = -1 ("Não informada") se ela ainda não existir.

    esquema_atributos: sk e atributos da dimensão (sem as colunas de SCD), na ordem de `valores`.
    """
    sk = esquema_atributos.split()[0]
    if ler(spark, "gold", dimensao).where(F.col(sk) == -1).limit(1).count():
        return
    membro = (
        spark.createDataFrame([valores], esquema_atributos)
        .withColumn("data_inicio", F.to_timestamp(F.lit(INICIO_VALIDADE)))
        .withColumn("data_fim", F.to_timestamp(F.lit(FIM_VALIDADE)))
        .withColumn("registro_atual", F.lit(True))
        .withColumn("hash_atributos", F.lit(None).cast("string"))
    )
    gravar(membro, "gold", dimensao, "append")


garantir_membro_desconhecido("dim_funcao", "sk_funcao bigint, codigo smallint, nome string, area string",
                             (-1, None, "Não informada", "Não informada"))
garantir_membro_desconhecido("dim_elemento_despesa",
                             "sk_elemento bigint, codigo string, nome string, grupo_despesa string",
                             (-1, None, "Não informado", "Outros"))


# ---------------------------------------------------------------------------------------------------------
# SCD tipo 2 com MERGE
#
# Padrão do Delta Lake: as linhas da Silver entram duas vezes no MERGE quando um atributo mudou.
# - Com _chave_merge = chave natural: casam com a versão atual e a FECHAM.
# - Com _chave_merge = nulo: não casam com nada e são INSERIDAS como a nova versão.
# Chaves novas entram só uma vez e são inseridas com validade desde 1900-01-01.
#
# A sk das linhas inseridas é calculada antes do MERGE: maior sk existente + 1, 2, 3... (no Databricks era uma
# coluna de identidade, que o Delta fora do Databricks não oferece de forma confiável).
# ---------------------------------------------------------------------------------------------------------

def hash_atributos(atributos):
    return F.sha2(F.concat_ws("||", *[F.coalesce(F.col(a).cast("string"), F.lit("∅")) for a in atributos]), 256)


def aplicar_scd2(dimensao, origem, chave, sk, atributos):
    """Aplica as linhas de `origem` (chave, atributos, atualizado_em) na dimensão."""
    origem = origem.withColumn("hash_atributos", hash_atributos(atributos))
    dim = ler(spark, "gold", dimensao)
    atual = dim.where(F.col("registro_atual") & F.col(chave).isNotNull())

    existentes = origem.join(atual.select(chave), chave, "left_semi")
    novas = origem.join(atual.select(chave), chave, "left_anti")
    alteradas = (
        origem.alias("o")
        .join(atual.alias("a"), F.col(f"o.{chave}") == F.col(f"a.{chave}"))
        .where(F.col("o.hash_atributos") != F.col("a.hash_atributos"))
        .select("o.*")
    )
    qtd_alteradas = alteradas.count()  # antes do MERGE: depois dele, os hashes já são iguais

    # Linhas que serão inseridas: chaves novas (válidas desde 1900) e nova versão das alteradas.
    a_inserir = (
        novas
        .withColumn("_chave_merge", F.col(chave))
        .withColumn("_inicio", F.to_timestamp(F.lit(INICIO_VALIDADE)))
        .unionByName(
            alteradas
            .withColumn("_chave_merge", F.lit(None).cast(origem.schema[chave].dataType))
            .withColumn("_inicio", F.col("atualizado_em"))
        )
    )
    maior_sk = dim.where(F.col(sk) > 0).agg(F.max(sk)).first()[0] or 0
    a_inserir = a_inserir.withColumn(
        "_sk", (F.lit(maior_sk) + F.row_number().over(Window.orderBy(chave, "_inicio"))).cast("bigint")
    )

    # Linhas das chaves existentes: só servem para fechar a versão atual quando o hash mudou.
    para_fechar = (
        existentes
        .withColumn("_chave_merge", F.col(chave))
        .withColumn("_inicio", F.to_timestamp(F.lit(INICIO_VALIDADE)))
        .withColumn("_sk", F.lit(None).cast("bigint"))
    )
    preparadas = para_fechar.unionByName(a_inserir)

    inserir = {c: f"novo.{c}" for c in [chave, *atributos, "hash_atributos"]}
    inserir.update({
        sk: "novo._sk",
        "data_inicio": "novo._inicio",
        "data_fim": f"TIMESTAMP'{FIM_VALIDADE}'",
        "registro_atual": "true",
    })

    (
        tabela_delta(spark, "gold", dimensao).alias("dim")
        .merge(preparadas.alias("novo"), f"dim.{chave} = novo._chave_merge AND dim.registro_atual")
        .whenMatchedUpdate(
            condition="dim.hash_atributos <> novo.hash_atributos",
            set={"registro_atual": "false", "data_fim": "novo.atualizado_em"},
        )
        .whenNotMatchedInsert(values=inserir)
        .execute()
    )

    versoes = ler(spark, "gold", dimensao).where(F.col(chave).isNotNull())
    print(f"{dimensao:<25} {versoes.where('registro_atual').count():>4} chaves  "
          f"{versoes.count():>4} versões  ({qtd_alteradas} alterada(s) nesta execução)")


# ---------------------------------------------------------------------------------------------------------
# Carga das dimensões
# ---------------------------------------------------------------------------------------------------------

# dim_municipio
aplicar_scd2(
    "dim_municipio",
    ler(spark, "silver", "municipio").select("ibge", "nome", "fonte", "data_coleta", "atualizado_em"),
    chave="ibge",
    sk="sk_municipio",
    atributos=["nome", "fonte", "data_coleta"],
)

# dim_funcao: a área do dashboard sai do código da função.
area = F.lit("Outras")
for codigo, nome in AREAS.items():
    area = F.when(F.col("codigo") == codigo, F.lit(nome)).otherwise(area)

aplicar_scd2(
    "dim_funcao",
    ler(spark, "silver", "funcao").select("codigo", "nome", area.alias("area"), "atualizado_em"),
    chave="codigo",
    sk="sk_funcao",
    atributos=["nome", "area"],
)

# dim_elemento_despesa: o grupo vem do mapeamento gerado por scripts/elemento_grupo.py.
mapa_grupo = (
    spark.read.option("header", "true").option("inferSchema", "false")
    .csv(publicar_referencia(spark, "elemento_grupo.csv"))
    .select(F.col("codigo_elemento").alias("codigo"), "grupo")
)
grupo = F.lit("Outros")
for codigo, nome in GRUPOS.items():
    grupo = F.when(F.col("grupo") == codigo, F.lit(nome)).otherwise(grupo)

elementos = (
    ler(spark, "silver", "elemento_despesa")
    .join(mapa_grupo, "codigo", "left")
    .select("codigo", "nome", grupo.alias("grupo_despesa"), "atualizado_em")
)
sem_grupo = [r["codigo"] for r in elementos.join(mapa_grupo, "codigo", "left_anti").collect()]
if sem_grupo:
    print(f"Aviso: elementos sem grupo no elemento_grupo.csv (ficam em 'Outros'): {sorted(sem_grupo)}")

aplicar_scd2(
    "dim_elemento_despesa",
    elementos,
    chave="codigo",
    sk="sk_elemento",
    atributos=["nome", "grupo_despesa"],
)

# dim_data: um dia por linha, do início de 2023 ao fim de 2026. É fixa, então é recriada a cada execução.
gravar(
    spark.sql("SELECT explode(sequence(DATE'2023-01-01', DATE'2026-12-31', INTERVAL 1 DAY)) AS data")
    .select(
        F.date_format("data", "yyyyMMdd").cast("int").alias("sk_data"),
        "data",
        F.year("data").alias("ano"),
        F.quarter("data").alias("trimestre"),
        F.month("data").alias("mes"),
        F.date_format("data", "yyyy-MM").alias("ano_mes"),
    ),
    "gold", "dim_data", "overwrite",
)
print(f"{'dim_data':<25} {ler(spark, 'gold', 'dim_data').count():>4} dias")


# ---------------------------------------------------------------------------------------------------------
# Conferência: cada chave natural deve ter exatamente uma versão atual, as versões de uma chave não podem se
# sobrepor no tempo, e a sk não pode se repetir (antes era garantida pela coluna de identidade).
# ---------------------------------------------------------------------------------------------------------

DIMENSOES_SCD = [
    ("dim_municipio", "ibge", "sk_municipio"),
    ("dim_funcao", "codigo", "sk_funcao"),
    ("dim_elemento_despesa", "codigo", "sk_elemento"),
]
for dimensao, chave, sk in DIMENSOES_SCD:
    completa = ler(spark, "gold", dimensao)
    dim = completa.where(F.col(chave).isNotNull())
    atuais_por_chave = dim.groupBy(chave).agg(F.sum(F.col("registro_atual").cast("int")).alias("atuais"))
    erradas = atuais_por_chave.where("atuais <> 1").count()
    sobrepostas = (
        dim.alias("a").join(dim.alias("b"), chave)
        .where((F.col(f"a.{sk}") != F.col(f"b.{sk}"))
               & (F.col("a.data_inicio") < F.col("b.data_fim"))
               & (F.col("b.data_inicio") < F.col("a.data_fim")))
        .count()
    )
    sk_repetidas = completa.groupBy(sk).count().where("count > 1").count()
    if erradas or sobrepostas or sk_repetidas:
        raise ValueError(f"{dimensao}: {erradas} chave(s) sem exatamente uma versão atual, "
                         f"{sobrepostas} par(es) de versões sobrepostas, {sk_repetidas} sk repetida(s)")

print("\nOK: dimensões conferidas (uma versão atual por chave, sem sobreposição, sk única).")

mostrar(
    ler(spark, "gold", "dim_elemento_despesa")
    .where("registro_atual")
    .groupBy("grupo_despesa").count()
    .orderBy("grupo_despesa")
)
spark.stop()
