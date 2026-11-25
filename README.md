# Despesas públicas da AMREC

Trabalho final de Engenharia de Dados.

## Descrição

O projeto organiza as despesas públicas dos 12 municípios da Associação dos Municípios da Região Carbonífera (AMREC), em Santa Catarina, de 2023 a 2026, em um banco PostgreSQL normalizado (3FN), hospedado no [Neon](https://neon.com). São 15 tabelas e 3,45 milhões de linhas, com 80% das tabelas acima de 10 mil linhas.

O fluxo tem três etapas:

1. **Coleta:** [notebooks/coleta.ipynb](notebooks/coleta.ipynb) baixa, registro a registro, as despesas dos 10 municípios que publicam no portal Betha e confere os arquivos exportados manualmente do portal Atende.net de Treviso e Morro da Fumaça.
2. **Tratamento:** [notebooks/tratamento.ipynb](notebooks/tratamento.ipynb) une as duas fontes, limpa e padroniza os dados, confere chaves e regras de domínio e gera um CSV por tabela.
3. **Carga:** os scripts em [sql/](sql) criam o esquema `origem`, carregam os CSVs e validam o resultado.

A partir do banco de origem, o pipeline leva os dados para um Lakehouse no [Databricks](docs/databricks.md) Free Edition, em camadas: Landing (CSV em um Volume) e Bronze, Silver e Gold (Delta Lake). As quatro camadas já estão implementadas, da ingestão incremental das 15 tabelas na Landing ao modelo dimensional na [Gold](docs/gold.md). Antes do Databricks, o grupo montou um MVP local com MinIO e Airflow, mantido como registro em [MVP local](docs/minio.md).

| Pasta ou arquivo | Conteúdo |
| --- | --- |
| [notebooks/coleta.ipynb](notebooks/coleta.ipynb) | Coleta dos dados brutos em `dados/brutos/amrec/` |
| [notebooks/tratamento.ipynb](notebooks/tratamento.ipynb) | Tratamento e geração dos CSVs em `dados/tratados/` |
| [sql/origem.sql](sql/origem.sql) | DDL do esquema `origem` |
| [sql/carga.sql](sql/carga.sql) | Carga dos CSVs no banco |
| [sql/validacao.sql](sql/validacao.sql) | Conferência da carga (somente leitura) |
| [databricks/](databricks) | Notebooks do Lakehouse: piloto, teste Delta e as camadas Landing, Bronze, Silver e Gold |
| [dags/](dags) | MVP local: DAG piloto do Airflow |
| [compose.airflow.yml](compose.airflow.yml) | MVP local: Airflow Standalone em Docker |
| [.env.example](.env.example) | MVP local: variáveis de acesso ao MinIO |
| [docs/](docs) | Documentação em MkDocs |

## Avisos

- **O exercício de 2026 é parcial.** Ele cobre os dados publicados até a coleta de 16 e 17/11/2026.
- **Os dados não ficam no Git.** Os brutos contêm CPF e CNPJ, e os tratados (~400 MB) passam do limite de arquivo do GitHub. A pasta `dados/` inteira está no `.gitignore`, e os notebooks reproduzem tudo.
- **Dados pessoais.** CPF nunca é gravado completo: o tratamento mascara no padrão `***XXXXXX**` os CPFs publicados inteiros, inclusive dentro de textos livres.
- **O `sql/origem.sql` apaga e recria o esquema `origem`.** O banco é inteiramente reproduzido a partir dos CSVs; não guarde nada no esquema que não venha da carga.
- **Limites do plano gratuito do Neon:** 1 GB de armazenamento (a base ocupa 771 MB) e 5 GB de transferência por mês. Uma extração completa de todas as tabelas transfere cerca de 0,5 GB; veja [Banco de origem](docs/banco.md#limites-do-plano-gratuito-do-neon).
- **Credenciais.** As strings de conexão do Neon ficam em `.env.neon`, fora do Git. No Databricks, o acesso ao Neon fica na conexão governada `neon_origem`, nunca nos notebooks. As credenciais do MVP local (MinIO) ficam em um `.env`, também fora do Git. Não commite esses arquivos nem compartilhe as credenciais fora da equipe.

## Pré-requisitos

| Ferramenta | Uso |
| --- | --- |
| Python 3.10 ou superior, com `pandas` e Jupyter | Rodar os notebooks |
| MkDocs 1.6 ([requirements-docs.txt](requirements-docs.txt)) | Abrir a documentação localmente |
| Cliente `psql` (PostgreSQL Command Line Tools) | Aplicar o DDL, carregar e validar os dados |
| Acesso ao projeto Neon `aged-dawn-21484247` | Banco de destino (PostgreSQL 18) |
| CLI do Neon (`npm i -g neon`) | Opcional. Gera o `.env.neon` com as strings de conexão |

## Instalação

Os comandos abaixo usam o PowerShell, na raiz do repositório.

1. Clone o repositório:

    ```powershell
    git clone https://github.com/02kamk/Trabalho_Final_Engenharia_de_Dados.git
    cd Trabalho_Final_Engenharia_de_Dados
    ```

2. Crie um ambiente virtual e instale as dependências:

    ```powershell
    python -m venv .venv
    .\.venv\Scripts\Activate.ps1
    python -m pip install pandas jupyter -r requirements-docs.txt
    ```

3. Confirme que o `psql` está instalado:

    ```powershell
    psql --version
    ```

4. Configure a conexão com o banco. Com acesso à organização no Neon, use a CLI:

    ```powershell
    neon login
    neon link --project-id aged-dawn-21484247 --no-env-pull -y
    neon env pull --file .env.neon
    ```

    Sem a CLI, peça a string de conexão ao responsável pelo projeto e grave-a em `.env.neon` como `DATABASE_URL_UNPOOLED=...`. Os detalhes estão em [Banco de origem](docs/banco.md).

5. Carregue a conexão direta na sessão do terminal:

    ```powershell
    $env:DATABASE_URL = (Get-Content .env.neon | Where-Object { $_ -like 'DATABASE_URL_UNPOOLED=*' }) -replace '^DATABASE_URL_UNPOOLED=', '' -replace '^"|"$', ''
    ```

## Como usar

### Coletar e tratar os dados

Rode os dois notebooks em ordem, do início ao fim (**Restart & Run All**):

1. `notebooks/coleta.ipynb`: leva algumas horas na primeira vez, porque o portal Betha entrega poucos registros por segundo. É retomável: se for interrompido, rode de novo e só o que falta é baixado. Os CSVs de Treviso e Morro da Fumaça são exportados à mão; as instruções estão no próprio notebook.
2. `notebooks/tratamento.ipynb`: gera os 15 CSVs em `dados/tratados/` em poucos minutos.

Para rodar pelo terminal no Windows, ative antes o modo UTF-8 (`$env:PYTHONUTF8 = "1"`), senão o `jupyter execute` corrompe os acentos do notebook.

### Criar o esquema e carregar os dados

Com a `DATABASE_URL` carregada, aplique o DDL e depois a carga. Os dois scripts rodam em uma única transação: se algo falhar, nada é gravado.

```powershell
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/origem.sql
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/carga.sql
```

### Consultar os dados

Exemplo: quantidade de empenhos por município e exercício.

```powershell
psql --dbname="$env:DATABASE_URL" -X -c "SELECT m.nome, e.ano, count(*) FROM origem.empenho e JOIN origem.municipio m USING (ibge) GROUP BY 1, 2 ORDER BY 1, 2;"
```

### Abrir a documentação

```powershell
python -m mkdocs serve
```

A documentação fica em http://127.0.0.1:8000.

## Testes

O projeto não tem testes automatizados de unidade. A integridade dos dados é conferida em dois pontos.

**No tratamento.** O notebook só exporta os CSVs se todas as conferências passarem: chaves primárias e únicas sem repetição, nenhuma das 18 chaves estrangeiras com órfãos, regras de domínio, nenhum CPF completo e o critério de 80% das tabelas com 10 mil linhas ou mais.

**Depois da carga.** O [sql/validacao.sql](sql/validacao.sql) só faz leitura:

```powershell
psql --dbname="$env:DATABASE_URL" -X -v ON_ERROR_STOP=1 -f sql/validacao.sql
Remove-Item Env:DATABASE_URL
```

Ele mostra cinco conferências:

1. Linhas por tabela e o critério de 10 mil linhas.
2. Restrições no catálogo do PostgreSQL, todas validadas.
3. Empenhos por município e exercício.
4. CPF completo gravado (o esperado é 0).
5. Tamanho do esquema.

O resultado da carga de 17/11/2026 está em [Validação](docs/validacao.md).

## Documentação

A documentação completa começa em [docs/index.md](docs/index.md):

- [Coleta da AMREC](docs/coleta-amrec.md): por que a base mudou, fontes avaliadas, coleta e defeitos encontrados nos arquivos.
- [Fontes e inventário](docs/fontes.md): consultas usadas e descartadas, colunas, granularidade e chaves.
- [Modelo de dados](docs/modelo.md): as 15 tabelas, colunas, chaves e decisões de normalização.
- [Banco de origem](docs/banco.md): Neon, carga e limites do plano gratuito.
- [Lakehouse no Databricks](docs/databricks.md): arquitetura em camadas, notebooks e ingestão incremental para a Landing.
- [Camada Gold](docs/gold.md): modelo dimensional, regras de negócio e indicadores.
- [MVP local (MinIO e Airflow)](docs/minio.md): primeira versão do data lake, substituída pelo Databricks.
- [Validação](docs/validacao.md): contagens, conferências e registros descartados.
