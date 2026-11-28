"""Pipeline da AMREC com o lake no Azure: ingestão Neon → Landing, Bronze, Silver e Gold (dimensões e fatos).

Cada tarefa roda um script de pipeline/ dentro do contêiner do Airflow (Spark em modo local). Uma tarefa só
começa se a anterior terminou com sucesso. As camadas Bronze, Silver e Gold entram nesta lista (ETAPAS) conforme
forem adaptadas para o Azure: basta acrescentar (nome_da_tarefa, script) na ordem de execução.

- Agendamento: todo dia às 06:00 (horário de Brasília).
- Uma execução por vez: duas execuções juntas leriam e gravariam os mesmos watermarks.
- Sem novas tentativas automáticas: uma falha indica um problema a corrigir. Depois de corrigir, rode de novo;
  cada camada só grava o controle depois da carga, e a Silver e a Gold usam MERGE, então nada é duplicado.
"""

from datetime import timedelta

import pendulum
from airflow.providers.standard.operators.bash import BashOperator
from airflow.sdk import dag

ETAPAS = [
    ("landing", "03_landing.py"),
    ("bronze", "04_bronze.py"),
    ("silver", "05_silver.py"),
    ("gold_dimensoes", "06_gold_dimensoes.py"),
    ("gold_fatos", "07_gold_fatos.py"),
]


@dag(
    dag_id="amrec_pipeline",
    start_date=pendulum.datetime(2026, 11, 25, tz="America/Sao_Paulo"),
    schedule="0 6 * * *",
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 0, "execution_timeout": timedelta(hours=1)},
    tags=["amrec", "pipeline"],
    doc_md=__doc__,
)
def amrec_pipeline():
    anterior = None
    for tarefa, script in ETAPAS:
        atual = BashOperator(task_id=tarefa, bash_command=f"python /opt/airflow/pipeline/{script}")
        if anterior is not None:
            anterior >> atual
        anterior = atual


amrec_pipeline()
