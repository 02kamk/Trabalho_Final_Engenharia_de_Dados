# Trabalho_Final_Engenharia_de_Dados

Despesas publicas de Criciuma, de 2023 a 2026.

A documentacao comeca em [docs/index.md](docs/index.md). Para abrir o MkDocs localmente:

```powershell
python -m pip install -r requirements-docs.txt
python -m mkdocs serve
```

## Base de dados para carga

Os 15 CSVs em [dados/origem-validada](dados/origem-validada) contêm 151.851 registros normalizados da coleta de 07/11/2026. O exercício de 2026 é parcial. Os arquivos estão no caminho esperado por `sql/carga_inicial.sql`, que usa o esquema definido em `sql/origem.sql`.

Na cópia pública, o campo `cpf_cnpj` de emendas está vazio e os identificadores detectados em campos de texto estão mascarados. As chaves relacionais e as contagens foram preservadas.
