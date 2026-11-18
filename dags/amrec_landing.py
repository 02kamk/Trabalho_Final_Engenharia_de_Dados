"""Exporta a tabela piloto do Neon para a camada Landing."""

import csv
import io
import logging
from contextlib import closing
from datetime import datetime, timezone
from hashlib import sha256

from airflow.providers.amazon.aws.hooks.s3 import S3Hook
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.sdk import dag, get_current_context, task
from botocore.exceptions import ClientError

BUCKET = "datalake-amrec"
log = logging.getLogger(__name__)


@dag(
    dag_id="amrec_landing_municipio",
    start_date=datetime(2026, 11, 18, tzinfo=timezone.utc),
    schedule=None,
    catchup=False,
    tags=["amrec", "landing"],
)
def amrec_landing_municipio():
    @task
    def exportar_municipio() -> None:
        neon = PostgresHook(postgres_conn_id="neon_origem")
        with closing(neon.get_conn()) as conexao, conexao.cursor() as cursor:
            cursor.execute("SELECT * FROM origem.municipio ORDER BY ibge")
            colunas = [coluna.name for coluna in cursor.description]
            registros = cursor.fetchall()

        if not registros:
            raise ValueError("origem.municipio retornou zero linhas")

        csv_memoria = io.StringIO(newline="")
        escritor = csv.writer(csv_memoria, lineterminator="\n")
        escritor.writerow(colunas)
        escritor.writerows(registros)
        conteudo = csv_memoria.getvalue().encode("utf-8")

        execucao = get_current_context()["dag_run"].run_id
        identificador = sha256(execucao.encode("utf-8")).hexdigest()[:24]
        caminho = f"landing/municipio/execucao-{identificador}.csv"
        minio = S3Hook(aws_conn_id="minio_amrec").get_conn()

        try:
            minio.put_object(
                Bucket=BUCKET,
                Key=caminho,
                Body=conteudo,
                ContentType="text/csv; charset=utf-8",
                IfNoneMatch="*",
            )
        except ClientError as erro:
            if erro.response["ResponseMetadata"]["HTTPStatusCode"] != 412:
                raise

        objeto = minio.get_object(Bucket=BUCKET, Key=caminho)
        with closing(objeto["Body"]) as corpo:
            if corpo.read() != conteudo:
                raise ValueError(f"O CSV no MinIO difere da exportação: {caminho}")

        log.info("CSV verificado em s3://%s/%s (%d linhas)", BUCKET, caminho, len(registros))

    exportar_municipio()


amrec_landing_municipio()
