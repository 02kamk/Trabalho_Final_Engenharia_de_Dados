# Airflow com Java, PySpark e Delta Lake para rodar o pipeline na VM.
# O Spark roda dentro do próprio contêiner (modo local) e grava no Azure Data Lake Storage.

# O Java vem pronto da imagem oficial Eclipse Temurin (baixada do Docker Hub por https), em vez do apt do
# Debian: os downloads do apt falharam várias vezes com "Hash Sum mismatch". O Temurin já traz os
# certificados (cacerts) que o Java usa para baixar os pacotes do Spark.
FROM eclipse-temurin:17-jre AS java

FROM apache/airflow:3.4.0-python3.11
COPY --from=java /opt/java/openjdk /opt/java/openjdk
ENV JAVA_HOME=/opt/java/openjdk
ENV PATH="/opt/java/openjdk/bin:${PATH}"

# Fixar a versão do Airflow evita que o pip o atualize junto com as outras bibliotecas.
# PySpark 3.5 + delta-spark 3.2 são compatíveis entre si; o Spark 3.5 usa o Hadoop 3.3.4,
# por isso o conector do Azure (hadoop-azure) é da mesma versão (ver pipeline/comum.py).
RUN pip install --no-cache-dir \
    "apache-airflow==${AIRFLOW_VERSION}" \
    "pyspark==3.5.3" \
    "delta-spark==3.2.1"
