"""Funções comuns dos scripts do pipeline: sessão Spark, caminhos do lake e conexão com o Neon.

O lake fica no Azure Data Lake Storage Gen2, no container definido em AZURE_CONTAINER. Cada camada é uma
pasta dentro dele (landing/, bronze/, silver/, gold/, controle/). As credenciais vêm das variáveis de
ambiente carregadas pelo compose a partir de .env e .env.neon, que ficam fora do Git.
"""

import os
from urllib.parse import parse_qs, unquote, urlparse

PACOTES_SPARK = ",".join([
    "io.delta:delta-spark_2.12:3.2.1",       # Delta Lake para o Spark 3.5
    "org.apache.hadoop:hadoop-azure:3.3.4",  # leitura e gravação em abfss://
    "org.postgresql:postgresql:42.7.4",      # leitura do Neon por JDBC
])


def variavel(nome):
    valor = os.environ.get(nome, "").strip().strip('"').strip("'")
    if not valor:
        raise RuntimeError(f"Variável de ambiente {nome} não definida. Confira o .env / .env.neon.")
    return valor


def raiz_lake():
    """abfss://<container>@<conta>.dfs.core.windows.net"""
    return f"abfss://{variavel('AZURE_CONTAINER')}@{variavel('AZURE_STORAGE_ACCOUNT')}.dfs.core.windows.net"


def caminho(camada, tabela):
    """Caminho de uma tabela no lake, por exemplo caminho('silver', 'empenho')."""
    return f"{raiz_lake()}/{camada}/{tabela}"


def criar_spark(nome_app, memoria_driver="3g"):
    """Sessão Spark local com Delta Lake e acesso ao Azure Data Lake Storage."""
    from pyspark.sql import SparkSession

    conta = variavel("AZURE_STORAGE_ACCOUNT")
    spark = (
        SparkSession.builder
        .appName(nome_app)
        .master("local[2]")
        .config("spark.jars.packages", PACOTES_SPARK)
        .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension")
        .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog")
        .config(f"spark.hadoop.fs.azure.account.key.{conta}.dfs.core.windows.net", variavel("AZURE_STORAGE_KEY"))
        .config("spark.driver.memory", memoria_driver)
        .config("spark.sql.session.timeZone", "UTC")
        .config("spark.sql.parquet.datetimeRebaseModeInWrite", "CORRECTED")
        .config("spark.sql.parquet.datetimeRebaseModeInRead", "CORRECTED")
        .config("spark.ui.enabled", "false")
        .getOrCreate()
    )
    spark.sparkContext.setLogLevel("WARN")
    return spark


def conexao_neon():
    """Converte a DATABASE_URL_UNPOOLED (postgresql://usuario:senha@host/banco?...) para o JDBC do Spark.

    Retorna (url_jdbc, propriedades). A senha nunca é impressa.
    """
    url = urlparse(variavel("DATABASE_URL_UNPOOLED"))
    if url.scheme not in ("postgres", "postgresql"):
        raise RuntimeError("DATABASE_URL_UNPOOLED precisa começar com postgresql://")
    sslmode = parse_qs(url.query).get("sslmode", ["require"])[0]
    porta = f":{url.port}" if url.port else ""
    url_jdbc = f"jdbc:postgresql://{url.hostname}{porta}{url.path}?sslmode={sslmode}"
    propriedades = {
        "user": unquote(url.username or ""),
        "password": unquote(url.password or ""),
        "driver": "org.postgresql.Driver",
        # Lê em blocos de 10 mil linhas, em vez de trazer a tabela inteira para a memória de uma vez.
        "fetchsize": "10000",
    }
    return url_jdbc, propriedades


def ler_neon(spark, consulta):
    """Executa uma consulta SQL no Neon e devolve um DataFrame. O filtro roda no próprio Postgres."""
    url_jdbc, propriedades = conexao_neon()
    return spark.read.jdbc(url_jdbc, f"({consulta}) AS consulta", properties=propriedades)


# ---------------------------------------------------------------------------------------------------------
# Tabelas Delta no lake. No Databricks as tabelas tinham nome (workspace.amrec_silver.empenho); aqui cada
# tabela é uma pasta: <lake>/<camada>/<tabela>. As tabelas de controle ficam na camada "controle".
# ---------------------------------------------------------------------------------------------------------

TABELAS_ORIGEM = [
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

# Formato em que a Landing grava o atualizado_em: microssegundos e fuso, para o watermark não perder precisão.
FORMATO_TIMESTAMP = "yyyy-MM-dd'T'HH:mm:ss.SSSSSSXXX"


def ler(spark, camada, tabela):
    """Lê uma tabela Delta do lake (equivale ao spark.table do Databricks)."""
    return spark.read.format("delta").load(caminho(camada, tabela))


def existe(spark, camada, tabela):
    """True se já existe uma tabela Delta nesse caminho (equivale ao spark.catalog.tableExists)."""
    from delta.tables import DeltaTable

    return DeltaTable.isDeltaTable(spark, caminho(camada, tabela))


def tabela_delta(spark, camada, tabela):
    """DeltaTable para MERGE (equivale ao DeltaTable.forName)."""
    from delta.tables import DeltaTable

    return DeltaTable.forPath(spark, caminho(camada, tabela))


def gravar(df, camada, tabela, modo):
    """Grava um DataFrame como Delta. modo: 'append', 'overwrite' ou 'errorifexists'."""
    escritor = df.write.format("delta").mode(modo)
    if modo == "overwrite":
        escritor = escritor.option("overwriteSchema", "true")
    elif modo == "append":
        escritor = escritor.option("mergeSchema", "true")
    escritor.save(caminho(camada, tabela))


def garantir_tabela(spark, camada, tabela, esquema):
    """Cria a tabela Delta vazia com o esquema dado, se ela ainda não existir (CREATE TABLE IF NOT EXISTS)."""
    if not existe(spark, camada, tabela):
        spark.createDataFrame([], esquema).write.format("delta").save(caminho(camada, tabela))


def apagar(spark, caminho_completo):
    """Apaga uma pasta do lake, com tudo dentro (equivale ao dbutils.fs.rm(..., recurse=True))."""
    jvm = spark.sparkContext._jvm
    pasta = jvm.org.apache.hadoop.fs.Path(caminho_completo)
    pasta.getFileSystem(spark.sparkContext._jsc.hadoopConfiguration()).delete(pasta, True)


def publicar_referencia(spark, arquivo):
    """Copia um arquivo de databricks/referencia/ (montado em /opt/airflow/referencia) para <lake>/referencia/.

    Devolve o caminho do arquivo no lake. Assim os CSVs de referência também ficam no lake, versionados no Git.
    """
    jvm = spark.sparkContext._jvm
    origem = jvm.org.apache.hadoop.fs.Path(f"file:///opt/airflow/referencia/{arquivo}")
    destino_txt = caminho("referencia", arquivo)
    destino = jvm.org.apache.hadoop.fs.Path(destino_txt)
    destino.getFileSystem(spark.sparkContext._jsc.hadoopConfiguration()).copyFromLocalFile(False, True, origem, destino)
    return destino_txt


def mostrar(df, linhas=100):
    """Mostra um DataFrame no log (equivale ao display do Databricks)."""
    df.show(linhas, truncate=False)
