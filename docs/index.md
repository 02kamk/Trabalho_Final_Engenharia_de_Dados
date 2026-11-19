# Despesas públicas da AMREC

Base de dados das despesas dos 12 municípios da Associação dos Municípios da Região Carbonífera (AMREC), em Santa Catarina, de 2023 a 2026. O exercício de 2026 é parcial.

| Etapa | Onde |
| --- | --- |
| Coleta | `notebooks/coleta.ipynb` · [Coleta da AMREC](coleta-amrec.md) |
| Inventário das fontes | [Fontes e inventário](fontes.md) |
| Modelo (15 tabelas em 3FN) | [Modelo de dados](modelo.md) · `sql/origem.sql` |
| Tratamento | `notebooks/tratamento.ipynb` |
| Carga e validação | [Banco de origem](banco.md) · [Validação](validacao.md) · `sql/carga.sql` · `sql/validacao.sql` |
| Data lake e ingestão | [Data lake no MinIO](minio.md) · `dags/` · `compose.airflow.yml` |
